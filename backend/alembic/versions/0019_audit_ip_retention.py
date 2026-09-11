"""Audit-Log: IP-Adressen nach 90 Tagen entfernen dürfen (Datensparsamkeit).

Das Audit-Log bleibt nur anhängbar. Einzige Ausnahme: die IP-Adresse eines Eintrags, der älter als
90 Tage ist, darf auf NULL gesetzt werden – sonst nichts. Die Frist steht hier in der Datenbank,
nicht in der App: Auch eine übernommene App kann frische Einträge nicht verändern.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-12 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WITH_IP_RETENTION = """
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
  -- Einzige erlaubte Änderung: IP eines über 90 Tage alten Eintrags entfernen
  IF TG_OP = 'UPDATE'
     AND OLD.ip IS NOT NULL AND NEW.ip IS NULL
     AND OLD.created_at < now() - interval '90 days'
     AND NEW.id = OLD.id
     AND NEW.created_at = OLD.created_at
     AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id
     AND NEW.event = OLD.event
     AND NEW.details = OLD.details THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'audit_log ist nur anhängbar';
END;
$$ LANGUAGE plpgsql;
"""

APPEND_ONLY = """
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log ist nur anhängbar';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(WITH_IP_RETENTION)


def downgrade() -> None:
    op.execute(APPEND_ONLY)
