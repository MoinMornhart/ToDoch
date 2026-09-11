#!/bin/sh
# Wählt die Caddy-Konfiguration nach TODOCH_TLS_MODE:
#   proxy     – nur HTTP auf Port 80, HTTPS macht ein vorgelagerter Reverse-Proxy
#   internal  – HTTPS mit eigener ToDoch-CA (Heimnetz, Zertifikat unter http://<IP>/ca.crt)
#   acme      – HTTPS mit Let's Encrypt (Domain muss öffentlich auf Port 80/443 zeigen)
set -eu
mode="${TODOCH_TLS_MODE:-internal}"
case "$mode" in
proxy | internal | acme) ;;
*)
	echo "TODOCH_TLS_MODE muss proxy, internal oder acme sein (ist: $mode)" >&2
	exit 1
	;;
esac
if [ "$mode" != proxy ] && [ -z "${TODOCH_DOMAIN:-}" ]; then
	echo "TODOCH_DOMAIN fehlt" >&2
	exit 1
fi
exec caddy run --config "/etc/caddy/Caddyfile.$mode" --adapter caddyfile
