# ADR 0003 – Valkey als Redis-Server

**Status:** angenommen (v0.0.1)

## Kontext

Rate-Limits und die Job-Warteschlange (ARQ) brauchen einen Redis-kompatiblen Server. Redis selbst
steht seit Version 7.4 nicht mehr unter einer BSD-Lizenz.

## Entscheidung

Im Compose-Stack läuft `valkey/valkey:8` (Linux Foundation, BSD-3-Clause), ein protokoll­kompatibler
Redis-Fork. Code und Konfiguration sprechen weiterhin „Redis“ (`TODOCH_REDIS_URL`, `redis-py`,
ARQ); ein Wechsel auf Redis ist ohne Codeänderung möglich.

Der Server hat ein Passwort (per stdin übergeben, nicht als Prozessargument), Append-Only-Persistenz
und hängt nur im internen Docker-Netz. Für die lokale Entwicklung ohne Server gibt es
`TODOCH_REDIS_URL=memory://` (fakeredis) – im Betrieb verboten.
