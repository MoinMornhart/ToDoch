"""Konfiguration aus Umgebungsvariablen (Präfix ``TODOCH_``).

Der Start bricht ab, wenn Secrets fehlen, zu kurz sind oder Platzhalter enthalten.
"""

from __future__ import annotations

import base64
import binascii
from functools import cached_property
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_MARKERS = ("change", "example", "placeholder", "xxx", "dummy", "default")


class ConfigError(ValueError):
    """Ungültige oder unsichere Konfiguration."""


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def parse_key_ring(raw: str) -> dict[int, bytes]:
    """``"1:<base64>,2:<base64>"`` → ``{1: key, 2: key}`` (je 32 Byte)."""
    keys: dict[int, bytes] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        kid_text, sep, b64 = part.partition(":")
        if not sep or not kid_text.isdigit():
            raise ConfigError("TODOCH_ENCRYPTION_KEYS: Format ist '1:<base64>,2:<base64>'")
        try:
            key = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ConfigError("TODOCH_ENCRYPTION_KEYS: Schlüssel ist kein gültiges Base64") from exc
        if len(key) != 32:
            raise ConfigError("TODOCH_ENCRYPTION_KEYS: jeder Schlüssel muss 32 Byte lang sein")
        keys[int(kid_text)] = key
    if not keys:
        raise ConfigError("TODOCH_ENCRYPTION_KEYS ist leer")
    return keys


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TODOCH_", extra="ignore")

    environment: Literal["production", "development", "test"] = "production"
    origin: str = Field(description="Öffentliche Adresse, z. B. https://todoch.example.de")
    secret_key: SecretStr
    encryption_keys: SecretStr
    encryption_key_active: int | None = None
    database_url: SecretStr
    redis_url: SecretStr
    setup_token: SecretStr | None = None

    session_idle_minutes: int = Field(default=720, ge=5, le=60 * 24 * 30)
    session_absolute_hours: int = Field(default=168, ge=1, le=24 * 90)
    max_body_bytes: int = Field(default=1_048_576, ge=1024)
    log_level: Literal["debug", "info", "warning", "error"] = "info"

    @field_validator("origin")
    @classmethod
    def _validate_origin(cls, value: str) -> str:
        value = value.rstrip("/")
        parts = urlsplit(value)
        if parts.scheme not in ("https", "http") or not parts.hostname:
            raise ValueError("muss eine vollständige URL wie https://todoch.example.de sein")
        if parts.path or parts.query or parts.fragment:
            raise ValueError("darf keinen Pfad enthalten")
        return value

    @model_validator(mode="after")
    def _validate_secrets(self) -> Settings:
        secret = self.secret_key.get_secret_value()
        if len(secret) < 32:
            raise ValueError("TODOCH_SECRET_KEY muss mindestens 32 Zeichen lang sein")
        if self.environment == "production":
            if _looks_like_placeholder(secret):
                raise ValueError("TODOCH_SECRET_KEY enthält einen Platzhalter")
            if urlsplit(self.origin).scheme != "https":
                raise ValueError("TODOCH_ORIGIN muss im Betrieb mit https:// beginnen")
            if self.redis_url.get_secret_value().startswith("memory://"):
                raise ValueError("TODOCH_REDIS_URL=memory:// ist nur zur Entwicklung erlaubt")
            db_password = urlsplit(self.database_url.get_secret_value()).password or ""
            if len(db_password) < 12 or _looks_like_placeholder(db_password):
                raise ValueError("Datenbank-Passwort fehlt, ist zu kurz oder ein Platzhalter")
        keys = parse_key_ring(self.encryption_keys.get_secret_value())
        if self.encryption_key_active is not None and self.encryption_key_active not in keys:
            raise ValueError(
                "TODOCH_ENCRYPTION_KEY_ACTIVE verweist auf keinen vorhandenen Schlüssel"
            )
        if self.setup_token is not None and len(self.setup_token.get_secret_value()) < 16:
            raise ValueError("TODOCH_SETUP_TOKEN muss mindestens 16 Zeichen lang sein")
        return self

    @cached_property
    def key_ring(self) -> dict[int, bytes]:
        return parse_key_ring(self.encryption_keys.get_secret_value())

    @property
    def active_key_id(self) -> int:
        return self.encryption_key_active or max(self.key_ring)

    @property
    def rp_id(self) -> str:
        host = urlsplit(self.origin).hostname
        assert host is not None
        return host

    @property
    def is_https(self) -> bool:
        return self.origin.startswith("https://")


def load_settings() -> Settings:
    try:
        return Settings()
    except ValueError as exc:  # pydantic.ValidationError erbt von ValueError
        raise ConfigError(f"Konfiguration ungültig:\n{exc}") from exc
