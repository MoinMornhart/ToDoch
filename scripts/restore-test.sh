#!/usr/bin/env bash
# Wiederherstellungstest: startet ToDoch mit Docker Compose, legt ein Konto an, sichert mit
# „todoch backup“, löscht die Daten, spielt die Sicherung wie „todoch restore“ zurück und prüft,
# dass alles wieder da ist und ToDoch läuft. Nutzt dieselben Funktionen wie der Befehl im
# Container (deploy/lxc/build.func) – getestet wird also genau das, was im Ernstfall läuft.
#
# Aufruf: scripts/restore-test.sh        (braucht Docker mit Compose und openssl)
# Eigenes Compose-Projekt „todoch-restore-test“ – eine echte Installation bleibt unberührt.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

work=$(mktemp -d)
export TODOCH_HOME=$PWD
export TODOCH_ENV="$work/todoch.env"
export TODOCH_BACKUPS="$work/backups"
export TODOCH_PROJECT="${TODOCH_PROJECT:-todoch-restore-test}"
# Git Bash unter Windows: Docker braucht Windows-Pfade in der Umgebungsdatei
env_file=$TODOCH_ENV
command -v cygpath >/dev/null && env_file=$(cygpath -m "$TODOCH_ENV")
# shellcheck source=../deploy/lxc/build.func
source deploy/lxc/build.func
color

cleanup() {
  stop_spinner
  todoch_compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

cat >"$TODOCH_ENV" <<EOF
TODOCH_ORIGIN=https://todoch.restore.test
TODOCH_DOMAIN=todoch.restore.test
TODOCH_TLS_MODE=internal
TODOCH_HTTP_PORT=${TODOCH_TEST_HTTP_PORT:-18080}
TODOCH_HTTPS_PORT=${TODOCH_TEST_HTTPS_PORT:-18443}
TODOCH_SECRET_KEY=$(openssl rand -hex 32)
TODOCH_ENCRYPTION_KEYS=1:$(openssl rand -base64 32)
TODOCH_SETUP_TOKEN=$(openssl rand -hex 12)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
REDIS_PASSWORD=$(openssl rand -hex 24)
TODOCH_ENVIRONMENT=production
TODOCH_LOG_LEVEL=warning
TODOCH_VERSION=${TODOCH_TEST_VERSION:-restore-test}
TODOCH_ENV_FILE=${env_file}
EOF

sql() { todoch_compose exec -T db psql -U todoch -d todoch -v ON_ERROR_STOP=1 -tAq -c "$1"; }

setup_required() {
  todoch_compose exec -T app python -c "import json, urllib.request
print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/meta'))['setup_required'])"
}

fail() {
  msg_error "$1"
  todoch_compose logs --tail 60 app worker db || true
  exit 1
}

expect() { # expect <was> <erwartet> <ist>
  [[ "$2" == "$3" ]] || fail "$1: erwartet „$2“, ist „$3“"
  msg_ok "$1"
}

msg_info "Baue und starte ToDoch"
todoch_compose up -d --build >/dev/null 2>&1 || fail "Compose-Start fehlgeschlagen"
wait_healthy || fail "ToDoch startet nicht"
msg_ok "ToDoch läuft"
expect "Frische Installation" "True" "$(setup_required)"

sql "INSERT INTO users (id, email, display_name, password_hash, password_changed_at,
     is_admin, is_active, timezone, locale)
     VALUES (gen_random_uuid(), 'restore@example.org', 'Restore', 'x', now(),
     true, true, 'Europe/Berlin', 'de')"
expect "Konto angelegt" "False" "$(setup_required)"
schema=$(sql "SELECT version_num FROM alembic_version")

msg_info "Sichere mit todoch backup"
file=$(todoch_backup restore-test)
[[ -s "$file" ]] || fail "Keine Sicherung erzeugt"
[[ -s "$TODOCH_BACKUPS/keys/todoch.env" ]] || fail "Die Schlüssel fehlen neben der Sicherung"
msg_ok "Sicherung: $(basename "$file")"

sql "DELETE FROM users"
expect "Daten gelöscht" "True" "$(setup_required)"

msg_info "Stelle die Sicherung wieder her"
todoch_restore_db "$file" || fail "Wiederherstellung fehlgeschlagen"
todoch_compose up -d >/dev/null 2>&1 || fail "Neustart fehlgeschlagen"
wait_healthy || fail "ToDoch startet nach der Wiederherstellung nicht"
msg_ok "ToDoch läuft wieder"
expect "Konto wiederhergestellt" "restore@example.org" "$(sql "SELECT email FROM users")"
expect "Datenbank-Stand ($schema)" "$schema" "$(sql "SELECT version_num FROM alembic_version")"
expect "Einrichtung abgeschlossen" "False" "$(setup_required)"
msg_ok "Wiederherstellungstest bestanden"
