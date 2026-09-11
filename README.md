<div align="center">

<img src="docs/images/logo.svg" width="88" alt="ToDoch-Logo">

# ToDoch

**Deutsch** · [English](README.en.md)

**Deine To-dos und Termine – auf deinem eigenen Server.**<br>
Minimalistisch, schnell mit der Tastatur, sicher ab Werk. Keine Cloud, kein Tracking.

[![CI](https://github.com/MoinMornhart/Todoch/actions/workflows/ci.yml/badge.svg)](https://github.com/MoinMornhart/Todoch/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/release/MoinMornhart/Todoch?label=Version&color=2459d6)](https://github.com/MoinMornhart/Todoch/releases)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-2459d6)](LICENSE)
[![Proxmox](https://img.shields.io/badge/Proxmox-1%20Befehl-E57000?logo=proxmox&logoColor=white)](#-installation-auf-proxmox)

[Installation](#-installation-auf-proxmox) ·
[Funktionen](#-funktionen) ·
[Adresse & HTTPS](#-adresse-https-und-passkeys) ·
[Verwaltung](#-verwaltung-im-container) ·
[Roadmap](#-roadmap) ·
[Entwicklung](#-entwicklung)

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/uebersicht-dunkel.png">
  <img src="docs/images/uebersicht.png" alt="ToDoch – Übersicht mit Aufgaben, Terminen und Bereichen" width="860">
</picture>

</div>

---

## ✨ Funktionen

### 🏠 Übersicht zum Start
Nach dem Öffnen begrüßt dich ToDoch mit allem Wichtigen auf einen Blick: heute fällig, überfällig,
die nächsten Termine, was demnächst ansteht und wie viel in jedem Bereich offen ist. Über **Neu**
(auf dem Handy der ➕-Knopf) legst du von überall eine Aufgabe oder einen Termin an.

<table>
<tr>
<td width="50%" valign="top">

### ⚡ Schnellerfassung
Eine Zeile tippen – ToDoch erkennt Datum, Uhrzeit, Priorität, Tags, Bereich und Wiederholung:

```text
Reifenwechsel buchen nächste Woche 8:30 !mittel #auto @privat
```

Versteht auch „am 15.10. um 9 Uhr“, „übermorgen“, „in 2 Wochen“, „jeden Dienstag“, „werktags“, „Monatsende“ …

</td>
<td width="50%" valign="top">

<img src="docs/images/schnellerfassung.png" alt="Schnellerfassung mit erkannten Angaben">

</td>
</tr>
<tr>
<td width="50%" valign="top">

<img src="docs/images/ticket.png" alt="Aufgabe als Ticket anlegen">

</td>
<td width="50%" valign="top">

### 📝 Aufgaben als Ticket
Über **Neu → Aufgabe** öffnet sich ein vollständiges Formular wie bei einem Ticket: Titel, Bereich,
Fälligkeit mit Uhrzeit, Priorität, Tags, Unterpunkte, Notizen mit Markdown und Wiederholungen –
täglich, an bestimmten Wochentagen, monatlich, jährlich, mit Intervall und Enddatum.

### 🗂️ Bereiche
„Arbeit“, „Privat“ und eigene Bereiche mit Farbe und Symbol. Ein Klick filtert alle Ansichten.
Pro Bereich legst du fest, welche Tage und Stunden der Kalender zeigt – z. B. Arbeit nur Mo–Fr, 8–18 Uhr.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### ⌨️ Tastatur zuerst

| Taste | Aktion |
| :---: | --- |
| <kbd>n</kbd> | Neue Aufgabe |
| <kbd>c</kbd> | Neuer Termin |
| <kbd>t</kbd> | Vereinbarten Termin eintragen |
| <kbd>/</kbd> | Suchen |
| <kbd>j</kbd> / <kbd>k</kbd> | Nächste / vorherige Aufgabe |
| <kbd>x</kbd> | Erledigt |
| <kbd>e</kbd> | Bearbeiten |
| <kbd>?</kbd> | Alle Kürzel |

</td>
<td width="50%" valign="top">

### 📅 Klare Ansichten
**Heute** (mit Überfälligem), **Demnächst** für die nächsten 7 Tage, **Alle offen**, **Erledigt** und jeder einzelne Tag – dazu eine Volltextsuche über Titel, Notizen und Tags.

### 📱 Überall
Installierbar als App (PWA) auf Smartphone und Desktop, **Dunkelmodus** per Klick oder automatisch nach Systemeinstellung, **Deutsch und Englisch** (auf der Anmeldeseite und per Knopf neben der Suche umschaltbar, auch Fehlermeldungen des Servers), barrierearm.

</td>
</tr>
</table>

<div align="center">
<img src="docs/images/mobil.png" alt="ToDoch auf dem Smartphone" width="260">
&nbsp;&nbsp;&nbsp;
<img src="docs/images/mobil-demnaechst.png" alt="Demnächst auf dem Smartphone" width="260">
</div>

<details>
<summary><b>Bearbeiten, Heute-Ansicht und Dunkelmodus ansehen</b></summary>
<br>
<img src="docs/images/bearbeiten.png" alt="Aufgabe bearbeiten">
<img src="docs/images/heute.png" alt="Ansicht „Heute“">
<img src="docs/images/heute-dunkel.png" alt="Ansicht „Heute“ im Dunkelmodus">
</details>

### 🗓️ Kalender

<img src="docs/images/kalender-woche.png" alt="Kalender in der Wochenansicht">

**Monat, Woche, Tag und Agenda** – Termine per Drag & Drop verschieben, Aufgaben mit Fälligkeit
erscheinen direkt daneben. Wiederkehrende Termine (auch „jeden letzten Freitag“) lassen sich als
**nur dieser / dieser und folgende / alle** bearbeiten. Ganztägige und mehrtägige Termine, Ort,
Videolink, Teilnehmer, Erinnerungen, **feste Termine** mit Rückfrage beim Verschieben und eine
**Warnung bei Überschneidungen** im selben Bereich. Die Termine des Tages stehen auch auf „Heute“.
Ist ein Bereich gewählt, zeigt der Kalender nur dessen Tage und Stunden (einstellbar unter *Bereiche*).

**In anderen Kalendern anzeigen:** Unter *Bereiche → Kalender abonnieren* erzeugst du einen geheimen
ICS-Link – für alle oder nur einen Bereich, mit allen Details, nur Titeln oder nur „Belegt“. Ein Klick
öffnet ihn in Apple Kalender, Google Kalender oder Outlook; jeder Link lässt sich einzeln widerrufen.
Google und Outlook.com holen den Kalender aus dem Internet – dafür muss ToDoch öffentlich erreichbar
sein (z. B. hinter einem Reverse-Proxy).

**Erinnerungen:** Unter *Einstellungen → Erinnerungen als Benachrichtigung* für jedes Gerät einschalten –
ToDoch meldet sich dann vor Terminen per Push, auch wenn die App geschlossen ist (auf dem iPhone nach
„Zum Home-Bildschirm“). Die nötigen Schlüssel erzeugt der Server selbst.

### 📞 Vereinbarte Termine

Termin beim Arzt am Telefon ausgemacht? Ein Formular für alles, was am Telefon, persönlich
oder per Post vereinbart wurde – mit <kbd>t</kbd> oder über **Neu → Vereinbarter Termin**:

- **Kontakt** mit Name, Firma, Telefon, E-Mail und Adresse – gespeicherte Kontakte werden beim
  Tippen vorgeschlagen (kein CRM, nur das Nötigste; verwaltbar unter *Einstellungen → Kontakte*)
- **Termin** mit Dauer, Ort (vor Ort, telefonisch, Video mit Link) und eigener Zeitzone
- **Vereinbarung**: per Telefon / persönlich / Post, Gesprächsdatum, Gesprächspartner
- **Notizen** in Markdown für Gesprächsinhalt, Aktenzeichen, was mitzubringen ist – durchsuchbar
- **Folgeaufgabe** wie „Unterlagen vorbereiten“, automatisch X Tage vorher fällig und mit dem Termin verknüpft
- Der **Entwurf** wird laufend auf dem Gerät gesichert – nichts geht beim Neuladen verloren
- Danach: **ICS herunterladen** (ohne interne Notizen), **per E-Mail senden** oder
  **weiterer Termin für denselben Kontakt**

### 🍿 Streamo × ToDoch

[Streamo](https://github.com/MoinMornhart/Streamo) weiß, welche Filme du dir vorgenommen hast,
wann neue Folgen erscheinen und was bald aus deinem Abo verschwindet – ToDoch holt das automatisch in
deinen Kalender:

1. In Streamo unter **Kalender** die Abo-Adresse kopieren
2. In ToDoch unter **Bereiche → Kalender einbinden** einfügen und einen Bereich wählen (z. B. „Streamo“)

Ab dann gleicht ToDoch den Kalender regelmäßig ab (einstellbar von 15 Minuten bis täglich, auf Knopfdruck
sofort): Plant du in Streamo einen Film für Samstag 20:15, steht er kurz darauf im ToDoch-Kalender –
mit Laufzeit, Sehplänen und neuen Episoden. Die Termine sind in ToDoch nur lesbar, geändert wird in Streamo.
Genauso lassen sich andere ICS-Kalender einbinden, etwa Feiertage oder ein Arbeitskalender.

Die Abo-Adresse wird verschlüsselt gespeichert; Adressen im Heimnetz (wie ein Streamo-Container) kann
nur ein Admin eintragen, interne Adressen des Servers sind gesperrt.

<details>
<summary><b>Monatsansicht ansehen</b></summary>
<br>
<img src="docs/images/kalender-monat.png" alt="Kalender in der Monatsansicht">
</details>

### 🔒 Sicher ab Werk

| | |
| --- | --- |
| 🔑 **Anmeldung** | **Passkeys** (Face ID, Touch ID, Windows Hello, Sicherheitsschlüssel) ohne Benutzernamen, Einrichtung nur mit Einmalcode, Argon2id-Passwörter mit Abgleich gegen Leak-Listen, Sperre mit wachsender Wartezeit nach Fehlversuchen |
| 🍪 **Sitzungen** | Serverseitig und einzeln widerrufbar, Geräteübersicht, „Überall abmelden“, Idle- und Absolut-Timeout |
| 🛡️ **Browser** | Strenge Content-Security-Policy ohne `unsafe-inline`, CSRF-Schutz, HSTS und alle wichtigen Security-Header |
| 🧾 **Nachvollziehbar** | Audit-Log, das sich per Datenbank-Trigger nicht nachträglich ändern lässt |
| 📦 **Betrieb** | Container ohne Root-Rechte, schreibgeschützt, Datenbank ohne offene Ports, keine Telemetrie, keine CDNs |

Details und Bedrohungsmodell: [docs/SECURITY.md](docs/SECURITY.md)

---

## 🚀 Installation auf Proxmox

Ein Befehl in der **Shell des Proxmox-Hosts** (als root) – im Stil der [community-scripts](https://community-scripts.github.io/ProxmoxVE/):

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MoinMornhart/Todoch/main/ct/todoch.sh)"
```

Das Skript fragt **Standard** oder **Erweitert** ab, erstellt einen unprivilegierten Debian-13-Container
(2 CPU · 2 GB RAM · 16 GB Disk), installiert Docker, erzeugt alle Schlüssel und startet ToDoch.
Am Ende steht die Adresse und ein **einmaliger Einrichtungslink** für dein Konto:

```text
🚀  ToDoch wurde erfolgreich installiert!
🌐  Adresse: https://todoch.local
💡  Erster Aufruf (legt das Admin-Konto an):
      https://todoch.local/setup#code=…
```

| In der Container-Konsole | |
| --- | --- |
| `update` | Neueste Version installieren – mit Sicherung vorher und automatischem Rückfall bei Problemen |
| `todoch help` | Domain, Ports, Benutzer, Sicherung, Protokolle |

Die Proxmox-Konsole des Containers ist ohne Passwort zugänglich.

<details>
<summary><b>Ohne Rückfragen installieren (z. B. per SSH)</b></summary>

<br>

Alle Einstellungen lassen sich per Variable vorgeben:

```bash
var_ctid=108 var_hostname=todoch var_domain=todoch.example.de var_proxy=yes \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MoinMornhart/Todoch/main/ct/todoch.sh)"
```

| Variable | Bedeutung |
| --- | --- |
| `var_ctid`, `var_hostname` | Container-ID und Hostname |
| `var_cpu`, `var_ram`, `var_disk` | Ressourcen (Standard 2 / 2048 MiB / 16 GB) |
| `var_bridge`, `var_net`, `var_gateway`, `var_vlan`, `var_mac` | Netzwerk (`var_net=dhcp` oder `IP/CIDR`) |
| `var_storage`, `var_template_storage` | Speicher für Container und Vorlage |
| `var_domain`, `var_tls` / `var_proxy=yes` | Adresse und HTTPS-Betriebsart (siehe unten) |

</details>

<details>
<summary><b>Docker Compose ohne Proxmox</b></summary>

<br>

```bash
git clone https://github.com/MoinMornhart/Todoch.git && cd Todoch
cp .env.example deploy/.env && chmod 600 deploy/.env   # Werte eintragen – jede Variable ist erklärt
docker compose -f deploy/docker-compose.yml up -d --build
```

Dann `https://<TODOCH_DOMAIN>/setup#code=<TODOCH_SETUP_TOKEN>` öffnen.
Dienste: `web` (Caddy + Oberfläche) · `app` (API) · `worker` (Hintergrund-Jobs) · `db` (PostgreSQL) · `redis` (Valkey).
Datenbank und Redis hängen in einem internen Netz ohne Internet und ohne offene Ports.

| Variable | Bedeutung |
| --- | --- |
| `TODOCH_ORIGIN` | Adresse genau wie im Browser, z. B. `https://todoch.example.de` |
| `TODOCH_DOMAIN`, `TODOCH_TLS_MODE` | Hostname und HTTPS-Betriebsart (`proxy` · `internal` · `acme`) |
| `TODOCH_HTTP_PORT`, `TODOCH_HTTPS_PORT` | Ports auf dem Host (Standard 80 / 443) |
| `TODOCH_SECRET_KEY` | Signaturschlüssel, mind. 32 Zeichen |
| `TODOCH_ENCRYPTION_KEYS` | Schlüssel für gespeicherte Zugangsdaten – **getrennt sichern!** |
| `TODOCH_SETUP_TOKEN` | Einmaliger Einrichtungscode |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | Interne Passwörter |
| `TODOCH_SESSION_IDLE_MINUTES`, `TODOCH_SESSION_ABSOLUTE_HOURS` | Abmeldung nach Inaktivität / spätestens |

ToDoch startet nicht, wenn Schlüssel fehlen, zu kurz sind oder noch Platzhalter enthalten.

</details>

---

## 🌐 Adresse, HTTPS und Passkeys

Passkeys funktionieren nur über **HTTPS mit festem Hostnamen** – nie über eine IP. Sie sind fest an
diesen Hostnamen gebunden: Wer die Domain später ändert, muss Passkeys neu hinzufügen (das Passwort
funktioniert weiter).
ToDoch kennt drei Betriebsarten, umschaltbar mit einem Befehl:

| Befehl | Passt, wenn … | HTTPS macht … |
| --- | --- | --- |
| `todoch domain todoch.example.de --proxy` | ein Reverse-Proxy davor sitzt (NetBird, Nginx Proxy Manager, Traefik) | der Proxy – ToDoch spricht nur HTTP auf Port 80 |
| `todoch domain todoch.home.arpa` | ToDoch nur im Heimnetz läuft | ToDoch mit eigener CA (Zertifikat unter `http://<IP>/ca.crt`) |
| `todoch domain todoch.example.de --acme` | die Domain direkt auf den Server zeigt, Ports 80/443 offen | ToDoch mit Let's Encrypt |
| `todoch domain --reset` | du zurück zum Standard willst | ToDoch unter `https://<hostname>.local` |

> **Reverse-Proxy:** Als Ziel `http://<IP-des-Containers>:80` eintragen – HTTP, nicht HTTPS. `todoch info` zeigt es jederzeit an.

<details>
<summary><b>Zertifikat der ToDoch-CA auf Geräten installieren</b> (nur Betriebsart „internal“)</summary>

<br>

| Gerät | So geht's |
| --- | --- |
| iPhone / iPad | `http://<IP>/ca.crt` öffnen → Einstellungen → Profil installieren → Allgemein → Info → Zertifikatsvertrauenseinstellungen → aktivieren |
| macOS | Datei doppelklicken → Schlüsselbundverwaltung → „Immer vertrauen“ |
| Windows | Datei doppelklicken → Zertifikat installieren → „Vertrauenswürdige Stammzertifizierungsstellen“ |
| Android | Einstellungen → Sicherheit → Verschlüsselung & Anmeldedaten → CA-Zertifikat installieren |

</details>

---

## 🛠️ Verwaltung im Container

```bash
todoch info                      # Adresse, Betriebsart, Zustand aller Dienste
todoch setup-code                # Einrichtungslink erneut anzeigen
todoch users                     # Benutzer auflisten
todoch reset-password <e-mail>   # Passwort vergessen? Neues Zufallspasswort
todoch backup                    # Datenbank sichern → /var/backups/todoch
todoch restore <datei>           # Sicherung einspielen (sichert vorher den aktuellen Stand)
todoch logs [app|web|db|worker]  # Protokolle ansehen
```

> [!IMPORTANT]
> Die Schlüssel für gespeicherte Zugangsdaten liegen **getrennt** von der Sicherung unter
> `/var/backups/todoch/keys/`. Beides zusammen an einem sicheren Ort aufbewahren – ohne Schlüssel keine
> Wiederherstellung. Vor jedem Update legt ToDoch automatisch eine Sicherung an.

<details>
<summary><b>Fehlersuche</b></summary>

<br>

| Problem | Lösung |
| --- | --- |
| Seite nicht erreichbar | `todoch info` und `todoch logs` |
| 502 hinter dem Reverse-Proxy | Ziel muss `http://<IP>:<HTTP-Port>` sein, nicht `https://` |
| Zertifikatswarnung | In der Betriebsart `internal` die CA unter `http://<IP>/ca.crt` installieren |
| Passwort vergessen | `todoch reset-password <e-mail>` |
| „Zu viele Versuche“ | Nach 5 Fehlversuchen wartet ToDoch zunehmend länger (bis 1 Stunde) |
| Deinstallieren | Proxmox: `pct stop <ID> && pct destroy <ID>` · Compose: `docker compose -f deploy/docker-compose.yml down -v` |

</details>

---

## 🗺️ Roadmap

| | Meilenstein | Inhalt |
| :---: | --- | --- |
| ✅ | **1 · Grundgerüst** | Anmeldung, Sitzungen, Bereiche, Aufgaben, Schnellerfassung, Suche, PWA, Proxmox-Quickstart |
| ✅ | **2 · Kalender** | Termine, Serien, Monat / Woche / Tag / Agenda, Drag & Drop, Konflikte, ICS-Abos für Apple, Google & Outlook, Erinnerungen per Push, Übersicht, Dunkelmodus |
| ✅ | **3 · Vereinbarte Termine** | Formular für am Telefon oder persönlich ausgemachte Termine, Kontaktvorschläge, Folgeaufgaben, lokaler Entwurf, ICS zum Weitergeben |
| ⏳ | **4 · E-Mail** | Eigener Bereich „E-Mail“ in der Navigation, Postfächer per IMAP, Regeln, automatische Terminerkennung, Bestätigungs-Inbox |
| ⏳ | **5 · Synchronisation** | Gmail & Microsoft per OAuth, Zwei-Wege-Sync mit CalDAV, Google und Microsoft |
| 🚧 | **6 · Passkeys** | ✅ Anmeldung mit Face ID / Touch ID / Windows Hello / Sicherheitsschlüssel · ⏳ TOTP, Wiederherstellungscodes |
| ⏳ | **7 · Gruppen** | Gemeinsame Bereiche, Rollen, Einladungen, Zuweisungen, Kommentare |
| ⏳ | **8 · Härtung** | Datenexport, Kontolöschung, Restore-Tests, Security-Review nach OWASP ASVS L2 |

Jede Änderung erscheint als neue Version (`0.0.1 → 0.0.2 → … → 0.0.9 → 0.1.0`) mit Beschreibung im
[Changelog](CHANGELOG.md) und in den [Releases](https://github.com/MoinMornhart/Todoch/releases).

---

## 👩‍💻 Entwicklung

<details>
<summary><b>Lokal starten und testen</b></summary>

<br>

Voraussetzungen: Python 3.12 mit [uv](https://docs.astral.sh/uv/), Node.js 24, PostgreSQL 16.

```bash
# Backend – API auf http://127.0.0.1:8000
cd backend && uv sync
export TODOCH_ENVIRONMENT=development TODOCH_ORIGIN=http://localhost:5173 \
  TODOCH_SECRET_KEY=dev-secret-key-0123456789-abcdefghij \
  TODOCH_ENCRYPTION_KEYS=1:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8= \
  TODOCH_DATABASE_URL=postgresql+asyncpg://todoch:todoch@localhost:5432/todoch \
  TODOCH_REDIS_URL=memory://
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload

# Frontend – http://localhost:5173 (leitet /api ans Backend weiter)
cd frontend && npm install && npm run dev
```

| Tests | Befehl |
| --- | --- |
| Backend (pytest, braucht PostgreSQL) | `cd backend && uv run pytest` |
| Frontend (Vitest) | `cd frontend && npm test` |
| Ende-zu-Ende gegen den Produktions-Build (Playwright) | `cd frontend && npx playwright test` |
| Screenshots für diese Seite | `SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts` |

Neue Version veröffentlichen: `scripts/release.sh "Kurzbeschreibung" "Änderung 1" "Änderung 2"`

</details>

**Technik:** FastAPI · PostgreSQL 16 · Valkey + ARQ · SvelteKit + TypeScript + Tailwind · Caddy · Docker Compose<br>
**Mehr:** [Architektur](docs/ARCHITECTURE.md) · [Sicherheit](docs/SECURITY.md) · [Entscheidungen](docs/adr/) · [API (OpenAPI)](docs/openapi.json)

<div align="center">
<br>
<sub>MIT-Lizenz · © 2026 MoinMornhart</sub>
</div>
