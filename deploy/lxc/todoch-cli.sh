#!/usr/bin/env bash
# Todoch – Verwaltung im Container (Befehl „todoch“).
# Copyright (c) 2026 MoinMornhart | Lizenz: MIT | https://github.com/MoinMornhart/Todoch
set -Eeuo pipefail

TODOCH_HOME="${TODOCH_HOME:-/opt/todoch}"
# shellcheck source=build.func
source "$TODOCH_HOME/deploy/lxc/build.func"
color

HELP="Todoch – Verwaltung

  todoch info                          Version, Adresse, Ports und Dienste anzeigen
  todoch domain <domain> --proxy       Hinter Reverse-Proxy (NetBird, NPM, Traefik): nur HTTP, Port 80
  todoch domain <domain>               Eigene Domain mit Todoch-eigener CA (Heimnetz)
  todoch domain <domain> --acme        Eigene Domain mit Let's Encrypt (Ports 80/443 öffentlich)
  todoch domain --reset                Zurück zu https://$(hostname 2>/dev/null || echo '<hostname>').local
  todoch port <https> [http]           Ports ändern (Standard 443 / 80); hinter Proxy: todoch port <http>

  todoch setup-code                    Link für die Ersteinrichtung anzeigen
  todoch users                         Benutzer auflisten
  todoch reset-password <e-mail>       Neues Zufallspasswort setzen (beendet alle Sitzungen)
  todoch make-admin <e-mail>           Verwaltungsrechte vergeben

  todoch backup                        Datenbank sichern (nach ${TODOCH_BACKUPS})
  todoch restore <datei>               Sicherung wiederherstellen
  todoch logs [dienst]                 Protokolle ansehen (app, worker, web, db, redis)
  todoch restart                       Alle Dienste neu starten
  todoch status                        Zustand der Dienste
  todoch version                       Installierte Version

  update                               Neueste Version installieren (mit Sicherung und Rückfall)
"

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    msg_error "Bitte als root ausführen."
    exit 1
  fi
}

valid_port() { [[ "$1" =~ ^[0-9]+$ ]] && (($1 >= 1 && $1 <= 65535)); }
host_ip() { hostname -I | awk '{print $1}'; }
http_suffix() { [[ "${1:-80}" == "80" ]] && echo "" || echo ":$1"; }

origin_for() {
  local domain=$1 mode=$2 https_port
  https_port=$(get_env TODOCH_HTTPS_PORT)
  if [[ "$mode" == "proxy" || "${https_port:-443}" == "443" ]]; then
    echo "https://${domain}"
  else
    echo "https://${domain}:${https_port}"
  fi
}

apply_config() {
  msg_info "Übernehme Einstellungen und starte neu"
  silent todoch_compose up -d
  if wait_healthy; then
    msg_ok "Todoch läuft"
  else
    msg_error "Todoch startet nicht – letzte Meldungen:"
    todoch_compose logs --tail 40 || true
    exit 1
  fi
}

passkey_hint() {
  echo -e "${INFO}${YW}Passkeys sind an die Adresse gebunden.${CL} Nach einem Adresswechsel einmal mit Passwort anmelden"
  echo -e "${TAB}   und unter ${BOLD}Einstellungen → Sicherheit${CL} einen neuen Passkey hinzufügen."
}

cmd_info() {
  local ip mode
  ip=$(host_ip)
  mode=$(get_env TODOCH_TLS_MODE)
  echo -e "\n  ${GN}Todoch${CL} v$(cat "$TODOCH_HOME/VERSION" 2>/dev/null)\n"
  echo -e "  Adresse:   ${BGN}$(get_env TODOCH_ORIGIN)${CL}"
  case "$mode" in
  proxy) echo -e "  HTTPS:     macht der Reverse-Proxy · Ziel: ${BOLD}http://${ip}$(http_suffix "$(get_env TODOCH_HTTP_PORT)")${CL}" ;;
  internal) echo -e "  HTTPS:     Todoch-CA · Zertifikat: ${BOLD}http://${ip}$(http_suffix "$(get_env TODOCH_HTTP_PORT)")/ca.crt${CL}" ;;
  acme) echo -e "  HTTPS:     Let's Encrypt" ;;
  esac
  echo -e "  Ports:     HTTP $(get_env TODOCH_HTTP_PORT) · HTTPS $(get_env TODOCH_HTTPS_PORT)"
  echo -e "  Dienste:"
  todoch_compose ps --format '    {{.Service}}: {{.State}} {{.Health}}' 2>/dev/null || true
  echo ""
}

cmd_domain() {
  need_root
  local domain="" mode="" reset=no arg old ip
  for arg in "$@"; do
    case "$arg" in
    --proxy) mode=proxy ;;
    --internal) mode=internal ;;
    --acme | --letsencrypt) mode=acme ;;
    --reset) reset=yes ;;
    -*)
      msg_error "Unbekannte Option: $arg"
      exit 1
      ;;
    *) domain=${arg,,} ;;
    esac
  done
  if [[ "$reset" == "yes" ]]; then
    domain="$(hostname).local"
    mode=internal
  elif [[ -z "$domain" ]]; then
    echo -e "Aktuelle Adresse: ${BGN}$(get_env TODOCH_ORIGIN)${CL} ($(get_env TODOCH_TLS_MODE))\n"
    echo "Aufruf: todoch domain <domain> [--proxy|--acme]   z. B.: todoch domain todoch.example.de --proxy"
    return
  fi
  domain=${domain#https://}
  domain=${domain#http://}
  domain=${domain%%/*}
  domain=${domain%%:*}
  if ! [[ "$domain" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]]; then
    msg_error "Ungültige Domain: ${domain}"
    exit 1
  fi
  mode=${mode:-internal}
  old=$(get_env TODOCH_ORIGIN)
  set_env TODOCH_DOMAIN "$domain"
  set_env TODOCH_TLS_MODE "$mode"
  set_env TODOCH_ORIGIN "$(origin_for "$domain" "$mode")"
  apply_config

  ip=$(host_ip)
  echo -e "\n${CM}${GN}Todoch ist jetzt eingestellt auf:${CL} ${BGN}$(get_env TODOCH_ORIGIN)${CL}  (vorher: ${old})\n"
  echo -e "${BOLD}Damit die Adresse funktioniert:${CL}"
  case "$mode" in
  proxy)
    echo -e "${TAB}1. DNS: ${BOLD}${domain}${CL} muss auf deinen Reverse-Proxy zeigen."
    echo -e "${TAB}2. Im Proxy als Ziel ${BOLD}http://${ip}$(http_suffix "$(get_env TODOCH_HTTP_PORT)")${CL} eintragen (HTTP, nicht HTTPS)."
    ;;
  internal)
    [[ "$domain" == *.local ]] || echo -e "${TAB}1. DNS: ${BOLD}${domain}${CL} muss auf ${BOLD}${ip}${CL} zeigen (Router, Pi-hole, AdGuard …)."
    echo -e "${TAB}2. Auf jedem Gerät einmal ${BOLD}http://${ip}$(http_suffix "$(get_env TODOCH_HTTP_PORT)")/ca.crt${CL} installieren und vertrauen."
    ;;
  acme)
    echo -e "${TAB}1. DNS: ${BOLD}${domain}${CL} muss auf deine öffentliche IP zeigen."
    echo -e "${TAB}2. Router: Ports 80 und 443 an ${BOLD}${ip}${CL} weiterleiten. Das Zertifikat kommt automatisch."
    ;;
  esac
  passkey_hint
}

cmd_port() {
  need_root
  local mode https=${1-} http=${2-}
  mode=$(get_env TODOCH_TLS_MODE)
  if [[ -z "$https" ]]; then
    echo -e "HTTP-Port: ${BOLD}$(get_env TODOCH_HTTP_PORT)${CL} · HTTPS-Port: ${BOLD}$(get_env TODOCH_HTTPS_PORT)${CL}"
    [[ "$mode" == "proxy" ]] && echo "Hinter dem Reverse-Proxy zählt nur der HTTP-Port: todoch port <http-port>"
    return
  fi
  if [[ "$mode" == "proxy" ]]; then
    valid_port "$https" || {
      msg_error "Ports müssen Zahlen zwischen 1 und 65535 sein."
      exit 1
    }
    set_env TODOCH_HTTP_PORT "$https"
  else
    http=${http:-$(get_env TODOCH_HTTP_PORT)}
    if ! valid_port "$https" || ! valid_port "$http" || [[ "$https" == "$http" ]]; then
      msg_error "Zwei verschiedene Ports zwischen 1 und 65535 angeben."
      exit 1
    fi
    set_env TODOCH_HTTPS_PORT "$https"
    set_env TODOCH_HTTP_PORT "$http"
    set_env TODOCH_ORIGIN "$(origin_for "$(get_env TODOCH_DOMAIN)" "$mode")"
  fi
  apply_config
  msg_ok "Ports: HTTP $(get_env TODOCH_HTTP_PORT) · HTTPS $(get_env TODOCH_HTTPS_PORT) · Adresse $(get_env TODOCH_ORIGIN)"
}

cmd_setup_code() {
  need_root
  echo -e "Einmaliger Link zum Anlegen des Admin-Kontos:\n"
  echo -e "  ${BGN}$(get_env TODOCH_ORIGIN)/setup#code=$(get_env TODOCH_SETUP_TOKEN)${CL}\n"
  echo "Der Code funktioniert nur, solange noch kein Konto existiert."
}

cmd_backup() {
  need_root
  local file
  msg_info "Sichere Datenbank"
  file=$(todoch_backup manuell)
  msg_ok "Sicherung: ${file}"
  echo -e "${INFO}${YW}Die Schlüssel für gespeicherte Zugangsdaten liegen getrennt unter ${TODOCH_BACKUPS}/keys/.${CL}"
  echo -e "${TAB}   Beides zusammen (z. B. auf einem USB-Stick) aufbewahren – ohne Schlüssel keine Wiederherstellung."
}

cmd_restore() {
  need_root
  local file=${1-} answer safety
  if [[ -z "$file" || ! -f "$file" ]]; then
    msg_error "Aufruf: todoch restore <datei>   (Sicherungen: ls ${TODOCH_BACKUPS})"
    exit 1
  fi
  if [[ "${2-}" != "--yes" ]]; then
    read -r -p "Aktuelle Daten werden durch ${file} ersetzt. Fortfahren? [j/N] " answer
    [[ "${answer,,}" == "j" || "${answer,,}" == "ja" ]] || exit 1
  fi
  msg_info "Sichere den aktuellen Stand"
  safety=$(todoch_backup vor-restore)
  msg_ok "Aktueller Stand gesichert: ${safety}"
  msg_info "Stelle ${file} wieder her"
  todoch_restore_db "$file"
  msg_ok "Datenbank wiederhergestellt"
  apply_config
}

run_admin() {
  todoch_compose exec -T app python -m app.cli "$@"
}

main() {
  case "${1-help}" in
  help | -h | --help) echo "$HELP" ;;
  info) cmd_info ;;
  domain)
    shift
    cmd_domain "$@"
    ;;
  port | ports)
    shift
    cmd_port "$@"
    ;;
  setup-code) cmd_setup_code ;;
  users) run_admin users ;;
  reset-password | make-admin)
    [[ -n "${2-}" ]] || {
      msg_error "Aufruf: todoch $1 <e-mail>"
      exit 1
    }
    run_admin "$1" "$2"
    ;;
  backup) cmd_backup ;;
  restore)
    shift
    cmd_restore "$@"
    ;;
  logs)
    shift
    todoch_compose logs -f --tail 100 "$@"
    ;;
  restart) apply_config && todoch_compose restart ;;
  status) todoch_compose ps ;;
  version) cat "$TODOCH_HOME/VERSION" ;;
  *)
    msg_error "Unbekannter Befehl: $1"
    echo "$HELP"
    exit 1
    ;;
  esac
}

main "$@"
