"""Verwaltung auf dem Server.  Im Container:  python -m app.cli <befehl>

Im Proxmox-LXC über den Befehl ``todoch`` erreichbar, z. B. ``todoch reset-password <e-mail>``.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, load_settings
from app.db import create_engine, create_sessionmaker
from app.models import User
from app.security.passwords import hash_password
from app.security.sessions import revoke_all_sessions
from app.services import audit


async def _find(db: AsyncSession, email: str) -> User | None:
    user: User | None = await db.scalar(select(User).where(User.email == email.strip().lower()))
    return user


async def run(command: str, email: str | None, settings: Settings) -> tuple[int, str]:
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        async with create_sessionmaker(engine)() as db:
            if command == "users":
                users = list(await db.scalars(select(User).order_by(User.created_at)))
                if not users:
                    return 0, "Noch keine Benutzer – Einrichtung mit „todoch setup-code“."
                lines = [
                    f"{u.email:<40} {u.display_name:<24} "
                    f"{'Admin' if u.is_admin else ''}{'' if u.is_active else ' (gesperrt)'}"
                    for u in users
                ]
                return 0, "\n".join(lines)

            user = await _find(db, email or "")
            if user is None:
                return 1, "Benutzer nicht gefunden."

            if command == "reset-password":
                password = secrets.token_urlsafe(18)
                user.password_hash = hash_password(password)
                user.password_changed_at = datetime.now(UTC)
                await revoke_all_sessions(db, user.id)
                audit.record(db, "password.reset_cli", user_id=user.id)
                await db.commit()
                return 0, (
                    f"Neues Passwort für {user.email}:\n\n    {password}\n\n"
                    "Alle Sitzungen wurden beendet. Bitte nach der Anmeldung unter "
                    "„Einstellungen“ ein eigenes Passwort setzen."
                )

            if command == "make-admin":
                user.is_admin = True
                audit.record(db, "role.admin_granted_cli", user_id=user.id)
                await db.commit()
                return 0, f"{user.email} hat jetzt Verwaltungsrechte."

            return 2, f"Unbekannter Befehl: {command}"
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="todoch", description="Todoch-Verwaltung")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("users", help="Benutzer auflisten")
    for name, text in (
        ("reset-password", "Neues Zufallspasswort setzen und alle Sitzungen beenden"),
        ("make-admin", "Verwaltungsrechte vergeben"),
    ):
        commands.add_parser(name, help=text).add_argument("email")
    args = parser.parse_args(argv)
    code, output = asyncio.run(run(args.command, getattr(args, "email", None), load_settings()))
    print(output, file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
