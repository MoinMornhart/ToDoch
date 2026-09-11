"""Englische Meldungen: je nach Accept-Language, und jede Meldung im Code hat eine Übersetzung."""

import ast
import re
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.i18n import EXACT, language_from, translate
from tests.conftest import ClientFactory

APP = Path(__file__).resolve().parent.parent / "app"
EN = {"Accept-Language": "en"}
# Interne Meldungen (Start-Konfiguration, Kryptografie, CLI) sind nicht für die Oberfläche
INTERNAL = {"config.py", "crypto.py", "cli.py"}
RAISERS = {
    "HTTPException",
    "_bad",
    "PasswordPolicyError",
    "RuleError",
    "ValueError",
    "_reject",
    "FeedError",
    "MailError",
    "OAuthError",
}


def _messages() -> set[str]:
    """Alle Meldungen, die per Exception zur Oberfläche gelangen – Platzhalter werden zu 7."""
    found: set[str] = set()
    for path in APP.rglob("*.py"):
        if path.name in INTERNAL or "quickadd" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "LOGIN_FAILED" for t in node.targets
            ):
                assert isinstance(node.value, ast.Constant)
                found.add(str(node.value.value))
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name not in RAISERS:
                continue
            for arg in [*node.args, *(k.value for k in node.keywords)]:
                if (
                    isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                    and " " in arg.value
                ):
                    found.add(arg.value)
                elif isinstance(arg, ast.JoinedStr):
                    found.add(
                        "".join(
                            str(v.value) if isinstance(v, ast.Constant) else "7" for v in arg.values
                        )
                    )
                elif isinstance(arg, ast.BinOp) and isinstance(arg.left, ast.Constant):
                    found.add(f"{arg.left.value}FREQ")
    return found


def test_every_message_has_an_english_version() -> None:
    messages = _messages()
    assert len(messages) > 40
    missing = sorted(m for m in messages if translate(m, "en") == m)
    assert missing == []


def test_translations_are_english() -> None:
    for text in EXACT.values():
        assert not re.search(r"[äöüÄÖÜß]", text), text


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "de"),
        ("", "de"),
        ("en", "en"),
        ("en-US,en;q=0.9", "en"),
        ("de-DE,de;q=0.9,en;q=0.8", "de"),
        ("fr-FR,en;q=0.5", "en"),
        ("fr", "de"),
    ],
)
def test_language_from_header(header: str | None, expected: str) -> None:
    assert language_from(header) == expected


def test_dynamic_messages() -> None:
    assert translate("Höchstens 20 Passkeys möglich.", "en") == "At most 20 passkeys allowed."
    assert translate("Nicht unterstützt: FOO", "en") == "Not supported: FOO"
    assert translate("Unbekannte Meldung", "en") == "Unbekannte Meldung"
    assert translate("Nicht gefunden.", "de") == "Nicht gefunden."


async def test_api_errors_follow_accept_language(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    fresh = await client_factory()
    anonymous = await fresh.get("/api/auth/me", headers=EN)
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"] == "Please sign in."
    missing = await alice.get("/api/tasks/00000000-0000-0000-0000-000000000000", headers=EN)
    assert missing.json()["detail"] == "Not found."
    german = await alice.get("/api/tasks/00000000-0000-0000-0000-000000000000")
    assert german.json()["detail"] == "Nicht gefunden."

    invalid = await alice.post(
        "/api/events",
        json={"title": "x", "start_date": "2026-09-14", "start_time": "09:00", "tzid": "Mars/X"},
        headers=EN,
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"][0]["msg"] == "Value error, Unknown time zone"


async def test_login_and_csrf_errors_in_english(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/login", json={"email": "x@example.org", "password": "falsch"}, headers=EN
    )
    assert r.json()["detail"] == "Email address or password is incorrect."
    no_csrf = await client.post("/api/auth/logout", headers={**EN, "X-CSRF-Token": "falsch"})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["detail"] == "CSRF check failed. Please reload the page."


async def test_rate_limit_keeps_retry_after(client: AsyncClient) -> None:
    last = None
    for _ in range(31):
        last = await client.post(
            "/api/auth/login", json={"email": "x@example.org", "password": "falsch"}, headers=EN
        )
    assert last is not None and last.status_code == 429
    assert last.json()["detail"] == "Too many attempts. Please try again later."
    assert "retry-after" in last.headers
