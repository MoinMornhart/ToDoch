#!/usr/bin/env bash
# Todoch – Installation im LXC-Container (wird von ct/todoch.sh aufgerufen).
# Richtet Docker ein, erzeugt alle Geheimnisse, baut und startet Todoch.
# Copyright (c) 2026 MoinMornhart | Lizenz: MIT | https://github.com/MoinMornhart/Todoch

set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8
REPO="${REPO:-MoinMornhart/Todoch}"
TODOCH_BRANCH="${TODOCH_BRANCH:-main}"
APP_TZ="${APP_TZ:-Europe/Berlin}"

echo "  ⏳ Bereite Container vor …"
apt-get update -qq >/dev/null
apt-get install -y -qq curl ca-certificates >/dev/null

source <(curl -fsSL -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/${REPO}/contents/deploy/lxc/build.func?ref=${TODOCH_BRANCH}" 2>/dev/null ||
  curl -fsSL "https://raw.githubusercontent.com/${REPO}/${TODOCH_BRANCH}/deploy/lxc/build.func?t=$(date +%s)")
color
catch_errors

install -d -m 700 /etc/todoch
if [[ "$TODOCH_BRANCH" != "main" ]]; then echo "$TODOCH_BRANCH" >/etc/todoch/branch; fi

msg_info "Aktualisiere Betriebssystem"
silent apt-get -y -o Dpkg::Options::=--force-confold upgrade
msg_ok "Betriebssystem aktuell"

msg_info "Installiere Abhängigkeiten"
silent apt-get install -y gnupg jq openssl avahi-daemon libnss-mdns
# Avahi (für https://<hostname>.local) in unprivilegierten Containern lauffähig machen
sed -i 's/^rlimit-nproc=/#rlimit-nproc=/' /etc/avahi/avahi-daemon.conf 2>/dev/null || true
systemctl enable -q --now avahi-daemon 2>/dev/null || true
msg_ok "Abhängigkeiten installiert"

msg_info "Installiere Docker"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${codename} stable" \
  >/etc/apt/sources.list.d/docker.list
silent apt-get update
silent apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
install -d /etc/docker
cat >/etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" }
}
EOF
systemctl enable -q docker
systemctl restart docker
silent docker info
msg_ok "Docker $(docker version --format '{{.Server.Version}}') installiert"

msg_info "Lade Todoch"
VERSION=$(latest_version || true)
if [[ -z "$VERSION" ]]; then
  msg_error "Die neueste Version konnte nicht ermittelt werden."
  exit 1
fi
download_release "$VERSION" "${TODOCH_RELEASES}/${VERSION}"
ln -sfn "${TODOCH_RELEASES}/${VERSION}" "$TODOCH_HOME"
msg_ok "Todoch v${VERSION} geladen"

msg_info "Erzeuge Konfiguration und Schlüssel"
domain="${DOMAIN:-}"
mode="${TLS_MODE:-}"
if [[ -z "$domain" ]]; then
  domain="$(hostname).local"
  mode=internal
fi
mode="${mode:-internal}"
(
  umask 077
  cat >"$TODOCH_ENV" <<EOF
# Todoch – Konfiguration (erzeugt bei der Installation am $(date +%F)).
# Ändern am besten mit „todoch domain …“ / „todoch port …“, danach wird automatisch neu gestartet.
# ACHTUNG: Enthält die Schlüssel für gespeicherte Zugangsdaten – getrennt sichern!

TODOCH_ORIGIN=https://${domain}
TODOCH_DOMAIN=${domain}
TODOCH_TLS_MODE=${mode}
TODOCH_HTTP_PORT=80
TODOCH_HTTPS_PORT=443

TODOCH_SECRET_KEY=$(openssl rand -hex 32)
TODOCH_ENCRYPTION_KEYS=1:$(openssl rand -base64 32)
TODOCH_SETUP_TOKEN=$(openssl rand -hex 12)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
REDIS_PASSWORD=$(openssl rand -hex 24)

TODOCH_ENVIRONMENT=production
TODOCH_LOG_LEVEL=info
TZ=${APP_TZ}
TODOCH_VERSION=${VERSION}
TODOCH_ENV_FILE=${TODOCH_ENV}
EOF
)
msg_ok "Konfiguration unter ${TODOCH_ENV} (nur root lesbar)"

msg_info "Baue Todoch – das dauert beim ersten Mal ein paar Minuten"
silent todoch_compose build --pull
msg_ok "Todoch gebaut"

msg_info "Starte Todoch"
silent todoch_compose up -d
if ! wait_healthy; then
  msg_error "Todoch startet nicht – letzte Meldungen:"
  todoch_compose logs --tail 60 || true
  exit 1
fi
msg_ok "Todoch läuft"

msg_info "Richte Konsole und Befehle ein"
write_helpers
systemctl restart container-getty@1.service 2>/dev/null || true
msg_ok "Konsole ohne Passwort · Befehle „update“ und „todoch“ verfügbar"

msg_info "Räume auf"
silent apt-get -y autoremove
silent apt-get -y autoclean
msg_ok "Aufgeräumt"
