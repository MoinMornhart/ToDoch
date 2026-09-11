import base64

import pytest

from app.config import ConfigError, Settings, parse_key_ring
from app.markdown import render_markdown
from app.security.crypto import Crypto, DecryptionError, sign, verify_signature
from app.security.leaked import is_leaked
from app.security.passwords import (
    PasswordPolicyError,
    check_password_policy,
    hash_password,
    verify_password,
)
from tests.conftest import TEST_KEY, make_settings

KEY2 = base64.b64encode(b"\x07" * 32).decode()


# --- Konfiguration ------------------------------------------------------------


def _production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "origin": "https://todoch.morncloud.de",
        "secret_key": "q" * 20 + "Z9k2Lm4Np6Rs8Tv0Wx1y",
        "database_url": "postgresql+asyncpg://todoch:Gk83hsKq0aP2@db/todoch",
    }
    values.update(overrides)
    return make_settings(**values)


def test_production_settings_accept_real_values() -> None:
    settings = _production()
    assert settings.rp_id == "todoch.morncloud.de"
    assert settings.is_https


@pytest.mark.parametrize(
    "overrides",
    [
        {"secret_key": "change-me-change-me-change-me-change-me"},
        {"secret_key": "zu-kurz"},
        {"origin": "http://todoch.morncloud.de"},
        {"origin": "https://todoch.morncloud.de/pfad"},
        {"database_url": "postgresql+asyncpg://todoch:CHANGE_ME@db/todoch"},
        {"encryption_keys": "1:abc"},
        {"encryption_keys": f"1:{TEST_KEY}", "encryption_key_active": 2},
        {"setup_token": "kurz"},
    ],
)
def test_insecure_settings_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _production(**overrides)


def test_key_ring_parsing() -> None:
    ring = parse_key_ring(f"1:{TEST_KEY}, 2:{KEY2}")
    assert set(ring) == {1, 2}
    with pytest.raises(ConfigError):
        parse_key_ring("x:abc")
    with pytest.raises(ConfigError):
        parse_key_ring("")


# --- Verschlüsselung ----------------------------------------------------------


def test_encrypt_roundtrip_and_context_binding() -> None:
    crypto = Crypto(parse_key_ring(f"1:{TEST_KEY}"), 1)
    token = crypto.encrypt("geheim", context="mail:1:password")
    assert "geheim" not in token
    assert crypto.decrypt_str(token, context="mail:1:password") == "geheim"
    with pytest.raises(DecryptionError):
        crypto.decrypt(token, context="mail:2:password")


def test_tampered_ciphertext_fails() -> None:
    crypto = Crypto(parse_key_ring(f"1:{TEST_KEY}"), 1)
    token = crypto.encrypt("geheim", context="c")
    tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
    with pytest.raises(DecryptionError):
        crypto.decrypt(tampered, context="c")
    with pytest.raises(DecryptionError):
        crypto.decrypt("kaputt", context="c")


def test_key_rotation() -> None:
    old = Crypto(parse_key_ring(f"1:{TEST_KEY}"), 1)
    token = old.encrypt("wert", context="c")
    both = Crypto(parse_key_ring(f"1:{TEST_KEY},2:{KEY2}"), 2)
    assert both.needs_rotation(token)
    rotated = both.rotate(token, context="c")
    assert not both.needs_rotation(rotated)
    only_new = Crypto(parse_key_ring(f"2:{KEY2}"), 2)
    assert only_new.decrypt_str(rotated, context="c") == "wert"


def test_signatures() -> None:
    sig = sign("s" * 32, "feed:1")
    assert verify_signature("s" * 32, "feed:1", sig)
    assert not verify_signature("s" * 32, "feed:2", sig)


# --- Passwörter ---------------------------------------------------------------


def test_hash_and_verify() -> None:
    hashed = hash_password("Korrekt-Pferd-Batterie")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "Korrekt-Pferd-Batterie") == (True, False)
    assert verify_password(hashed, "falsch")[0] is False
    assert verify_password("kein-hash", "x")[0] is False


def test_leaked_list() -> None:
    assert is_leaked("123456789")
    assert is_leaked("PASSWORD1")
    assert not is_leaked("Korrekt-Pferd-Batterie-Heftklammer")


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("kurz", "too_short"),
        ("a" * 300, "too_long"),
        ("abababababababab", "too_simple"),
        ("Mein-Name-ist-Alice-2026", "personal"),
        ("1qaz2wsx3edc", "leaked"),
        ("Q1W2E3R4T5Y6", "leaked"),
    ],
)
def test_password_policy(password: str, code: str) -> None:
    with pytest.raises(PasswordPolicyError) as info:
        check_password_policy(password, email="alice@example.org", display_name="Alice")
    assert info.value.code == code


def test_password_policy_accepts_good_password() -> None:
    check_password_policy("Korrekt-Pferd-Batterie-Heftklammer", email="alice@example.org")


# --- Markdown -----------------------------------------------------------------


def test_markdown_is_sanitized() -> None:
    html = render_markdown(
        "**fett** <script>alert(1)</script> [x](javascript:alert(1)) [ok](https://a.de)"
        "\n\n<img src=x onerror=alert(1)>"
    )
    assert "<strong>fett</strong>" in html
    assert "<script" not in html
    assert 'href="javascript' not in html
    assert "<img" not in html
    assert 'href="https://a.de"' in html
    assert 'rel="noopener noreferrer nofollow"' in html
