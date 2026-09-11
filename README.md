# Todoch

**Minimalistische To-do- und Termin-App – selbst gehostet, sicher, ohne Cloud.**

Todoch läuft auf deinem eigenen Server (z. B. Proxmox), braucht zur Laufzeit keine externen
Dienste, keine CDNs und sendet keine Telemetrie. Die Oberfläche ist eine installierbare Web-App
(PWA) für Desktop und Smartphone und lässt sich komplett mit der Tastatur bedienen.

> **Stand:** Version 0.0.1 = Meilenstein 1 (Grundgerüst) von 8. Welche Funktionen noch kommen,
> steht in der [Roadmap](#roadmap). Jede Änderung erscheint als neue Version in der
> [CHANGELOG.md](CHANGELOG.md).

## Funktionen

- **Aufgaben** mit Notiz (Markdown), Fälligkeit, Priorität, Tags, Unterpunkten und Wiederholungen
  (täglich, wöchentlich an bestimmten Tagen, monatlich, jährlich, mit Intervall und Enddatum).
- **Ansichten:** Heute, Demnächst (7 Tage), Alle offen, Erledigt, einzelne Tage – gefiltert nach
  **Bereichen** wie „Arbeit“ und „Privat“ (eigene Bereiche mit Farbe und Symbol möglich).
- **Schnellerfassung** in einer Zeile:
  `Rechnung zahlen morgen 14:00 !hoch #finanzen @arbeit` → Aufgabe mit Datum, Uhrzeit, Priorität,
  Tag und Bereich. Versteht auch „am 15.10. um 9 Uhr“, „nächsten Freitag“, „in 2 Wochen“,
  „jeden Dienstag“, „werktags“, „Monatsende“ …
- **Volltextsuche** über Titel, Notizen und Tags.
- **Tastatur:** `n` neue Aufgabe · `/` suchen · `j`/`k` navigieren · `x` abhaken · `e` bearbeiten · `?` Hilfe.
- **Sicherheit:** Einrichtung per Einmalcode, Argon2id-Passwörter mit Leak-Prüfung, serverseitige
  Sitzungen, CSRF-Schutz, Rate-Limits, strenge CSP, Audit-Log – Details in [docs/SECURITY.md](docs/SECURITY.md).
- Deutsch und Englisch, Hell- und Dunkelmodus (folgt dem System), barrierearm.

## Proxmox-Quickstart

Im Stil der [community-scripts](https://community-scripts.github.io/ProxmoxVE/): in der
**Shell des Proxmox-Hosts** (als root) ausführen:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MoinMornhart/Todoch/main/ct/todoch.sh)"
```

Das Skript fragt „Standard“ oder „Erweitert“ ab und erstellt einen unprivilegierten
**Debian-13-LXC** (2 CPU, 2 GB RAM, 16 GB Disk). Darin installiert es Docker, erzeugt alle
Geheimnisse, baut Todoch und startet es. Am Ende zeigt es die Adresse und einen **einmaligen
Einrichtungslink** für das Admin-Konto an.

- **Konsole ohne Passwort:** Die Proxmox-Konsole des Containers meldet sich automatisch als root an.
- **Update:** In der Konsole `update` eingeben. Todoch lädt die neueste Version, sichert vorher die
  Datenbank, spielt System-Updates ein und kehrt bei Problemen automatisch zur alten Version zurück.
- **Verwaltung:** `todoch help` (Domain, Ports, Benutzer, Sicherung, Protokolle).

### Ohne Rückfragen (z. B. per SSH)

Alle Einstellungen lassen sich vorgeben:

```bash
var_ctid=108 var_hostname=todoch var_mac=BC:24:11:00:00:01 \
var_domain=todoch.example.de var_proxy=yes \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MoinMornhart/Todoch/main/ct/todoch.sh)"
```

Weitere Variablen: `var_cpu`, `var_ram`, `var_disk`, `var_bridge`, `var_net` (`dhcp` oder
`IP/CIDR`), `var_gateway`, `var_vlan`, `var_storage`, `var_template_storage`, `var_tls`
(`proxy` | `internal` | `acme`).

## Adresse, HTTPS und Passkeys

Passkeys (ab Meilenstein 6) funktionieren nur über **HTTPS mit einem festen Hostnamen** – nie
über eine IP. Todoch kennt drei Betriebsarten, umschaltbar in der Container-Konsole:

| Befehl | Wann | HTTPS |
| --- | --- | --- |
| `todoch domain todoch.example.de --proxy` | Ein Reverse-Proxy (NetBird, Nginx Proxy Manager, Traefik) macht HTTPS | Proxy; Todoch nur HTTP auf Port 80 |
| `todoch domain todoch.home.arpa` | Nur im Heimnetz | Eigene Todoch-CA; Zertifikat unter `http://<IP>/ca.crt` auf jedem Gerät installieren |
| `todoch domain todoch.example.de --acme` | Domain zeigt direkt auf den Server, Ports 80/443 offen | Let's Encrypt automatisch |
| `todoch domain --reset` | Zurück zum Standard | `https://<hostname>.local` mit eigener CA |

**Beispiel NetBird / Nginx Proxy Manager:** `todoch domain todoch.example.de --proxy`, dann im Proxy
als Ziel `http://<IP-des-Containers>:80` eintragen (HTTP, nicht HTTPS). `todoch info` zeigt das
Ziel jederzeit an. Ports ändern: `todoch port <https> [http]` bzw. hinter dem Proxy `todoch port <http>`.

**Zertifikat der Todoch-CA installieren** (nur Betriebsart „internal“):
iPhone/iPad: Profil laden → Einstellungen → Profil installieren → Allgemein → Info →
Zertifikatsvertrauenseinstellungen → aktivieren. macOS: Doppelklick → Schlüsselbund → „Immer
vertrauen“. Windows: Doppelklick → Zertifikat installieren → „Vertrauenswürdige
Stammzertifizierungsstellen“. Android: Einstellungen → Sicherheit → Verschlüsselung &
Anmeldedaten → CA-Zertifikat installieren.

## Docker Compose (ohne Proxmox)

Für eine bestehende VM oder einen vorhandenen Docker-Host:

```bash
git clone https://github.com/MoinMornhart/Todoch.git && cd Todoch
cp .env.example deploy/.env      # Werte eintragen – jede Variable ist dort erklärt
chmod 600 deploy/.env
docker compose -f deploy/docker-compose.yml up -d --build
```

Danach `https://<TODOCH_DOMAIN>/setup#code=<TODOCH_SETUP_TOKEN>` öffnen. Die Dienste: `app`
(API), `worker` (Hintergrund-Jobs), `db` (PostgreSQL), `redis` (Valkey), `web` (Caddy + Oberfläche).
Datenbank und Redis hängen in einem internen Netz ohne Internet und ohne offene Ports.

### Konfiguration (`.env`)

| Variable | Bedeutung |
| --- | --- |
| `TODOCH_ORIGIN` | Öffentliche Adresse, genau wie im Browser (z. B. `https://todoch.example.de`) |
| `TODOCH_DOMAIN` | Hostname für Caddy |
| `TODOCH_TLS_MODE` | `proxy`, `internal` oder `acme` (siehe oben) |
| `TODOCH_HTTP_PORT`, `TODOCH_HTTPS_PORT` | Ports auf dem Host (Standard 80/443) |
| `TODOCH_SECRET_KEY` | Signaturschlüssel, mind. 32 Zeichen |
| `TODOCH_ENCRYPTION_KEYS` | Schlüssel für gespeicherte Zugangsdaten (`1:<base64>`, mehrere für Rotation) – **getrennt sichern!** |
| `TODOCH_SETUP_TOKEN` | Einmaliger Einrichtungscode für das erste Konto |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | Interne Passwörter |
| `TODOCH_SESSION_IDLE_MINUTES`, `TODOCH_SESSION_ABSOLUTE_HOURS` | Abmeldung nach Inaktivität / spätestens nach |
| `TZ`, `TODOCH_LOG_LEVEL`, `TODOCH_VERSION` | Zeitzone, Protokollstufe, Image-Version |

Todoch startet nicht, wenn Geheimnisse fehlen, zu kurz sind oder noch Platzhalter enthalten.

## Sicherung und Wiederherstellung

```bash
todoch backup                 # → /var/backups/todoch/todoch-<datum>-manuell.tar.gz
todoch restore <datei>        # sichert vorher den aktuellen Stand
```

Die Sicherung enthält die Datenbank. Die **Schlüssel** (Umgebungsdatei) liegen getrennt unter
`/var/backups/todoch/keys/` – ohne sie lassen sich gespeicherte Zugangsdaten nicht entschlüsseln.
Beides zusammen an einem sicheren Ort aufbewahren. Vor jedem Update legt Todoch automatisch eine
Sicherung an. Zusätzlich empfohlen: vor größeren Updates einen Proxmox-Snapshot des Containers.

## Fehlersuche

- **Seite nicht erreichbar:** `todoch info` zeigt Adresse, Betriebsart und den Zustand der Dienste,
  `todoch logs` die Protokolle (`todoch logs app`, `… web`, `… db`).
- **502 hinter dem Reverse-Proxy:** Ziel muss `http://<IP>:<HTTP-Port>` sein, nicht `https://`.
- **Zertifikatswarnung:** In der Betriebsart `internal` die CA unter `http://<IP>/ca.crt` installieren.
- **Passwort vergessen:** `todoch reset-password <e-mail>` setzt ein Zufallspasswort.
- **Zu viele Anmeldeversuche:** Nach fünf Fehlversuchen wartet Todoch zunehmend länger (bis 1 Stunde).

## Deinstallation

Auf dem Proxmox-Host: `pct stop <ID> && pct destroy <ID>`. Mit Docker Compose:
`docker compose -f deploy/docker-compose.yml down -v` (löscht auch alle Daten).

## Roadmap

| Meilenstein | Inhalt | Stand |
| --- | --- | --- |
| 1 | Grundgerüst: Auth mit Passwort + Sitzungen, Bereiche, Aufgaben, Oberfläche, CI | ✅ v0.0.1 |
| 2 | Kalender: Termine, Monat/Woche/Agenda, Erinnerungen, ICS-Feeds | |
| 3 | Formular für telefonisch vereinbarte Termine, Kontakte, Folgeaufgaben | |
| 4 | E-Mail: IMAP + Autoconfig, Regeln, Terminerkennung, Bestätigungs-Inbox | |
| 5 | OAuth für Gmail/Microsoft, Kalender-Synchronisation (CalDAV, Google, Microsoft, ICS) | |
| 6 | Passkeys, TOTP, Wiederherstellungscodes | |
| 7 | Gruppen, Rollen, Einladungen, Zuweisungen, Kommentare, Verlauf | |
| 8 | Härtung: Audit-Ansicht, Export/Kontolöschung, Restore-Tests, Security-Review nach OWASP ASVS L2 | |

## Entwicklung

Voraussetzungen: Python 3.12 mit [uv](https://docs.astral.sh/uv/), Node.js 24, PostgreSQL 16.

```bash
# Backend (API auf http://127.0.0.1:8000)
cd backend
uv sync
export TODOCH_ENVIRONMENT=development TODOCH_ORIGIN=http://localhost:5173 \
  TODOCH_SECRET_KEY=dev-secret-key-0123456789-abcdefghij \
  TODOCH_ENCRYPTION_KEYS=1:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8= \
  TODOCH_DATABASE_URL=postgresql+asyncpg://todoch:todoch@localhost:5432/todoch \
  TODOCH_REDIS_URL=memory://
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload

# Frontend (http://localhost:5173, leitet /api an das Backend weiter)
cd frontend && npm install && npm run dev
```

Tests: `uv run pytest` (Backend, braucht PostgreSQL – `TODOCH_TEST_DATABASE_URL`),
`npm test` (Unit), `npx playwright test` (Ende-zu-Ende gegen den Produktions-Build).
Architektur und Entscheidungen: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/adr/](docs/adr/).

## Versionen

Jede Änderung wird als neue Version veröffentlicht: `0.0.1 → 0.0.2 → … → 0.0.9 → 0.1.0`.
Commit-Nachricht, Tag `vX.Y.Z`, GitHub-Release und [CHANGELOG.md](CHANGELOG.md) beschreiben,
was sich geändert hat.

```bash
scripts/release.sh "Kurzbeschreibung" "Änderung 1" "Änderung 2"
```

## Lizenz

MIT © 2026 MoinMornhart
