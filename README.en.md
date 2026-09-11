<div align="center">

<img src="docs/images/logo.svg" width="88" alt="ToDoch logo">

# ToDoch

[Deutsch](README.md) · **English** · 🌐 **[Website & docs](https://moinmornhart.github.io/ToDoch/en/)**

**Your to-dos and appointments – on your own server.**<br>
Minimalist, fast from the keyboard, secure by default. No cloud, no tracking.

[![CI](https://github.com/MoinMornhart/Todoch/actions/workflows/ci.yml/badge.svg)](https://github.com/MoinMornhart/Todoch/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/release/MoinMornhart/Todoch?label=Version&color=2459d6)](https://github.com/MoinMornhart/Todoch/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-2459d6)](LICENSE)
[![Proxmox](https://img.shields.io/badge/Proxmox-1%20command-E57000?logo=proxmox&logoColor=white)](#-installation-on-proxmox)

[Installation](#-installation-on-proxmox) ·
[Features](#-features) ·
[Address & HTTPS](#-address-https-and-passkeys) ·
[Administration](#-administration-inside-the-container) ·
[Roadmap](#-roadmap) ·
[Development](#-development)

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/en/uebersicht-dunkel.png">
  <img src="docs/images/en/uebersicht.png" alt="ToDoch – overview with tasks, events and areas" width="860">
</picture>

<sub>Switch between English and German on the sign-in page or with the language button next to the search.</sub>

</div>

---

## ✨ Features

### 🏠 Overview on start
ToDoch greets you with everything important at a glance: due today, overdue, the next events,
what's coming up and how much is open in each area. Use **New** (the ➕ button on phones) to add a
task or an event from anywhere.

<table>
<tr>
<td width="50%" valign="top">

### ⚡ Quick add
Type one line – ToDoch detects date, time, priority, tags, area and recurrence:

```text
Book tyre change next week 8:30am !medium #car @private
```

Understands English and German, e.g. “on October 3rd at 9”, “the day after tomorrow”,
“in 2 weeks”, “every Tuesday and Friday”, “weekdays”, “tomorrow evening”, “end of the month” –
or „am 15.10. um 9 Uhr“, „übermorgen“, „jeden Dienstag“.

</td>
<td width="50%" valign="top">

<img src="docs/images/en/schnellerfassung.png" alt="Quick add with detected details">

</td>
</tr>
<tr>
<td width="50%" valign="top">

<img src="docs/images/en/ticket.png" alt="Create a task as a ticket">

</td>
<td width="50%" valign="top">

### 📝 Tasks as tickets
**New → Task** opens a complete form like a ticket: title, area, due date and time, priority,
tags, checklist, Markdown notes and recurrence – daily, on specific weekdays, monthly, yearly,
with interval and end date.

### 🗂️ Areas
“Work”, “Private” and your own areas with colour and icon. One click filters every view.
Per area you decide which days and hours the calendar shows – e.g. work only Mon–Fri, 8–18.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### ⌨️ Keyboard first

| Key | Action |
| :---: | --- |
| <kbd>n</kbd> | New task |
| <kbd>c</kbd> | New event |
| <kbd>/</kbd> | Search |
| <kbd>j</kbd> / <kbd>k</kbd> | Next / previous task |
| <kbd>x</kbd> | Done |
| <kbd>e</kbd> | Edit |
| <kbd>?</kbd> | All shortcuts |

</td>
<td width="50%" valign="top">

### 📅 Clear views
**Today** (including overdue), **Upcoming** for the next 7 days, **All open**, **Done** and every
single day – plus full-text search across titles, notes and tags.

### 📱 Everywhere
Installable as an app (PWA) on phone and desktop, **dark mode** with one click or following your
system, **German and English** (switchable on the sign-in page and with the button next to the
search, including server error messages), accessible.

</td>
</tr>
</table>

<div align="center">
<img src="docs/images/en/mobil.png" alt="ToDoch on a phone" width="260">
&nbsp;&nbsp;&nbsp;
<img src="docs/images/en/mobil-demnaechst.png" alt="Upcoming on a phone" width="260">
</div>

<details>
<summary><b>See editing, the Today view and dark mode</b></summary>
<br>
<img src="docs/images/en/bearbeiten.png" alt="Edit a task">
<img src="docs/images/en/heute.png" alt="Today view">
<img src="docs/images/en/heute-dunkel.png" alt="Today view in dark mode">
</details>

### 🗓️ Calendar

<img src="docs/images/en/kalender-woche.png" alt="Calendar week view">

**Month, week, day and agenda** – move events by drag & drop, tasks with a due date appear right
next to them. Recurring events (even “every last Friday”) can be edited as **only this / this and
following / all**. All-day and multi-day events, location, video link, attendees, reminders,
**fixed appointments** that ask before being moved and a **warning on overlaps** within the same
area. Today's events also show up on “Today”. When an area is selected, the calendar shows only its
days and hours (configurable under *Areas*).

**Show in other calendars:** Under *Areas → Subscribe to calendar* you create a secret ICS link –
for all areas or just one, with all details, titles only or just “busy”. One click opens it in
Apple Calendar, Google Calendar or Outlook; every link can be revoked on its own. Google and
Outlook.com fetch the calendar from the internet – ToDoch has to be publicly reachable for that
(e.g. behind a reverse proxy).

**Reminders:** Enable *Settings → Reminders as notifications* on each device – ToDoch then notifies
you before events via push, even when the app is closed (on iPhone after “Add to Home Screen”). The
server generates the required keys itself.

### 🍿 Streamo × ToDoch

[Streamo](https://github.com/MoinMornhart/Streamo) knows which films you plan to watch, when new
episodes air and what is about to leave your subscriptions – ToDoch brings all of that into your
calendar automatically:

1. In Streamo, copy the subscription address under **Calendar**
2. In ToDoch, paste it under **Areas → Add calendars** and pick an area (e.g. “Streamo”)

From then on ToDoch keeps the calendar in sync (every 15 minutes up to daily, or instantly at the push
of a button): plan a film in Streamo for Saturday 8:15 pm and it shows up in your ToDoch calendar
shortly after – with running time, watch plans and new episodes. The events are read-only in ToDoch;
you change them in Streamo. Any other ICS calendar works the same way, e.g. public holidays or a work
calendar.

The subscription address is stored encrypted; addresses in your home network (like a Streamo
container) can only be added by an admin, and the server's internal addresses are blocked.

<details>
<summary><b>See the month view</b></summary>
<br>
<img src="docs/images/en/kalender-monat.png" alt="Calendar month view">
</details>

### 🔄 Google Calendar & Outlook – both ways

**No setup at all (subscription link):** under **Areas**, click “Create subscription link”, then
“Add to Google Calendar” or “Add to Outlook” – your ToDoch events show up there and on your phone.
The other way round, copy the private calendar link from Google or Outlook (ToDoch links the right
settings page) and paste it under “Add calendars”. Requirement: ToDoch is reachable from the
internet; Google and Outlook refresh subscriptions only every few hours.

**Nextcloud, iCloud & co. (CalDAV) – no setup:** under **Areas → Sync online calendars**, pick the
provider (Nextcloud, iCloud, mailbox.org, Posteo, GMX, WEB.DE or your own server), enter your user
name and app password, click “Find calendars”, done – real two-way sync without any app
registration. For Nextcloud, the address of your server is enough.

**Real two-way sync with Google/Outlook:** under **Areas → Sync online calendars**, pick an area and click “Connect Google
Calendar” or “Connect Outlook calendar”: events of that area show up at the provider, and what you
add there shows up in ToDoch – changes and deletions both ways, every 5 minutes or at the push of a
button. Requires `todoch oauth google` once (plus enabling the “Google Calendar API”) or
`todoch oauth microsoft` (plus the `Calendars.ReadWrite` permission). Single modified occurrences of
a series are not synced yet.

### 📬 Email

A separate **Email** section in the navigation: add a mailbox via IMAP (the server is suggested for
Gmail, iCloud, GMX, Web.de, T-Online, Posteo, mailbox.org and others), read and search your mail and
**turn an email into a task** with one click – the subject becomes the title, the email is quoted in
the notes.

- ToDoch **only reads along**: nothing on the server is deleted, moved or marked as read
- Emails are always shown as **plain text** – images, scripts and tracking pixels are never loaded
- Encrypted connections only (SSL/TLS or STARTTLS with certificate checks); the password is stored
  encrypted and never shown again
- The background worker fetches new mail regularly (every 15 minutes by default)
- **Appointment suggestions:** calendar invitations (.ics) and phrases like “Meeting tomorrow 3pm” or
  „Termin am 15.10. um 14:30“ are detected and wait under *Appointment suggestions* – one click on
  “Add to calendar” adds them; nothing lands in your calendar unasked

- **Rules:** “sender contains *stadtwerke* and subject contains *invoice*” → automatically a task in
  the *Private* area with priority and tags, or mark newsletters as read right away. Plain text
  matching (no regular expressions), can also be applied to existing emails

**Gmail and Outlook/Hotmail with one click:** click “Connect with Google” or “Connect with
Microsoft”, sign in with the provider, done – no app password, no server settings. An admin runs
`todoch oauth google` or `todoch oauth microsoft` once in the container; the command explains step by
step where to get the client ID and secret. ToDoch only stores an encrypted refresh token, never your
Google or Microsoft password.

### 🔒 Secure by default

| | |
| --- | --- |
| 🔑 **Sign-in** | **Passkeys** (Face ID, Touch ID, Windows Hello, security keys) without a username, **two-factor** with an authenticator app and recovery codes, setup only with a one-time code, Argon2id passwords checked against leak lists, lockout with increasing delay after failed attempts |
| 🍪 **Sessions** | Server-side and individually revocable, device overview, “Sign out everywhere”, idle and absolute timeout |
| 🛡️ **Browser** | Strict Content Security Policy without `unsafe-inline`, CSRF protection, HSTS and all important security headers |
| 🧾 **Traceable** | Audit log that cannot be altered afterwards (database triggers) |
| 📦 **Operations** | Non-root, read-only containers, database without open ports, no telemetry, no CDNs |

Details and threat model: [docs/SECURITY.md](docs/SECURITY.md) (German)

---

## 🚀 Installation on Proxmox

One command in the **Proxmox host shell** (as root) – in the style of the
[community scripts](https://community-scripts.github.io/ProxmoxVE/):

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MoinMornhart/Todoch/main/ct/todoch.sh)"
```

The script asks for **Default** or **Advanced**, creates an unprivileged Debian 13 container
(2 CPU · 2 GB RAM · 16 GB disk), installs Docker, generates all keys and starts ToDoch. At the end it
prints the address and a **one-time setup link** for your account:

```text
🚀  ToDoch wurde erfolgreich installiert!
🌐  Adresse: https://todoch.local
💡  Erster Aufruf (legt das Admin-Konto an):
      https://todoch.local/setup#code=…
```

| In the container console | |
| --- | --- |
| `update` | Install the latest version – with a backup first and automatic rollback on problems |
| `todoch help` | Domain, ports, users, backup, logs |

The Proxmox console of the container is accessible without a password.

<details>
<summary><b>Unattended installation (e.g. via SSH)</b></summary>

<br>

Every setting can be passed as a variable:

```bash
var_ctid=108 var_hostname=todoch var_domain=todoch.example.com var_proxy=yes \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MoinMornhart/Todoch/main/ct/todoch.sh)"
```

| Variable | Meaning |
| --- | --- |
| `var_ctid`, `var_hostname` | Container ID and hostname |
| `var_cpu`, `var_ram`, `var_disk` | Resources (default 2 / 2048 MiB / 16 GB) |
| `var_bridge`, `var_net`, `var_gateway`, `var_vlan`, `var_mac` | Network (`var_net=dhcp` or `IP/CIDR`) |
| `var_storage`, `var_template_storage` | Storage for container and template |
| `var_domain`, `var_tls` / `var_proxy=yes` | Address and HTTPS mode (see below) |

</details>

<details>
<summary><b>Docker Compose without Proxmox</b></summary>

<br>

```bash
git clone https://github.com/MoinMornhart/Todoch.git && cd Todoch
cp .env.example deploy/.env && chmod 600 deploy/.env   # fill in the values – every variable is explained
docker compose -f deploy/docker-compose.yml up -d --build
```

Then open `https://<TODOCH_DOMAIN>/setup#code=<TODOCH_SETUP_TOKEN>`.
Services: `web` (Caddy + UI) · `app` (API) · `worker` (background jobs) · `db` (PostgreSQL) · `redis` (Valkey).
Database and Redis live in an internal network without internet access and without open ports.

| Variable | Meaning |
| --- | --- |
| `TODOCH_ORIGIN` | Address exactly as in the browser, e.g. `https://todoch.example.com` |
| `TODOCH_DOMAIN`, `TODOCH_TLS_MODE` | Hostname and HTTPS mode (`proxy` · `internal` · `acme`) |
| `TODOCH_HTTP_PORT`, `TODOCH_HTTPS_PORT` | Ports on the host (default 80 / 443) |
| `TODOCH_SECRET_KEY` | Signing key, at least 32 characters |
| `TODOCH_ENCRYPTION_KEYS` | Keys for stored credentials – **back them up separately!** |
| `TODOCH_SETUP_TOKEN` | One-time setup code |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | Internal passwords |
| `TODOCH_SESSION_IDLE_MINUTES`, `TODOCH_SESSION_ABSOLUTE_HOURS` | Sign-out after inactivity / at the latest |

ToDoch refuses to start if keys are missing, too short or still contain placeholders.

</details>

---

## 🌐 Address, HTTPS and passkeys

Passkeys only work over **HTTPS with a fixed hostname** – never via an IP address. They are bound to
that hostname: if you change the domain later, you have to add your passkeys again (your password
keeps working).
ToDoch knows three modes, switchable with one command:

| Command | Fits when … | HTTPS is handled by … |
| --- | --- | --- |
| `todoch domain todoch.example.com --proxy` | a reverse proxy sits in front (NetBird, Nginx Proxy Manager, Traefik) | the proxy – ToDoch only speaks HTTP on port 80 |
| `todoch domain todoch.home.arpa` | ToDoch only runs in your home network | ToDoch with its own CA (certificate at `http://<IP>/ca.crt`) |
| `todoch domain todoch.example.com --acme` | the domain points straight at the server, ports 80/443 open | ToDoch with Let's Encrypt |
| `todoch domain --reset` | you want to go back to the default | ToDoch at `https://<hostname>.local` |

> **Reverse proxy:** Use `http://<container-IP>:80` as the target – HTTP, not HTTPS. `todoch info` shows it at any time.

<details>
<summary><b>Install the ToDoch CA certificate on devices</b> (“internal” mode only)</summary>

<br>

| Device | How |
| --- | --- |
| iPhone / iPad | Open `http://<IP>/ca.crt` → Settings → Install profile → General → About → Certificate Trust Settings → enable |
| macOS | Double-click the file → Keychain Access → “Always Trust” |
| Windows | Double-click the file → Install certificate → “Trusted Root Certification Authorities” |
| Android | Settings → Security → Encryption & credentials → Install CA certificate |

</details>

---

## 🛠️ Administration inside the container

```bash
todoch info                      # address, mode, status of all services
todoch setup-code                # show the setup link again
todoch users                     # list users
todoch reset-password <email>    # forgot your password? new random password
todoch disable-2fa <email>       # lost your authenticator app? turn off two-factor
todoch oauth google              # set up “Connect with Google” (same for: microsoft)
todoch backup                    # back up the database → /var/backups/todoch
todoch restore <file>            # restore a backup (backs up the current state first)
todoch logs [app|web|db|worker]  # view logs
```

> [!IMPORTANT]
> The keys for stored credentials are kept **separately** from the backup in
> `/var/backups/todoch/keys/`. Store both together in a safe place – no restore without the keys.
> ToDoch creates a backup automatically before every update.

<details>
<summary><b>Troubleshooting</b></summary>

<br>

| Problem | Solution |
| --- | --- |
| Page not reachable | `todoch info` and `todoch logs` |
| 502 behind the reverse proxy | The target must be `http://<IP>:<HTTP port>`, not `https://` |
| Certificate warning | In `internal` mode install the CA from `http://<IP>/ca.crt` |
| Forgot password | `todoch reset-password <email>` |
| “Too many attempts” | After 5 failed attempts ToDoch waits increasingly longer (up to 1 hour) |
| Uninstall | Proxmox: `pct stop <ID> && pct destroy <ID>` · Compose: `docker compose -f deploy/docker-compose.yml down -v` |

</details>

---

## 🗺️ Roadmap

| | Milestone | Content |
| :---: | --- | --- |
| ✅ | **1 · Foundation** | Sign-in, sessions, areas, tasks, quick add, search, PWA, Proxmox quickstart |
| ✅ | **2 · Calendar** | Events, series, month / week / day / agenda, drag & drop, conflicts, ICS subscriptions for Apple, Google & Outlook, push reminders, overview, dark mode |
| ✅ | **4 · Email** | Own “Email” section, mailboxes via IMAP, task from email, automatic appointment detection with confirmation inbox, rules |
| ✅ | **5 · Sync** | Gmail & Microsoft via OAuth (“Connect with …”), two-way sync with Google Calendar, Outlook and CalDAV (Nextcloud, iCloud & co.), subscription links without setup |
| ✅ | **6 · Passkeys & two-factor** | Passkeys (Face ID / Touch ID / Windows Hello / security keys), two-factor with an authenticator app (TOTP), recovery codes |
| ⏳ | **7 · Groups** | Shared areas, roles, invitations, assignments, comments |
| ⏳ | **8 · Hardening** | Data export, account deletion, restore tests, security review against OWASP ASVS L2 |

Every change ships as a new version (`0.0.1 → 0.0.2 → … → 0.0.9 → 0.1.0`) with a description in the
[changelog](CHANGELOG.md) (German) and the [releases](https://github.com/MoinMornhart/Todoch/releases).

---

## 👩‍💻 Development

<details>
<summary><b>Run and test locally</b></summary>

<br>

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 24, PostgreSQL 16.

```bash
# Backend – API at http://127.0.0.1:8000
cd backend && uv sync
export TODOCH_ENVIRONMENT=development TODOCH_ORIGIN=http://localhost:5173 \
  TODOCH_SECRET_KEY=dev-secret-key-0123456789-abcdefghij \
  TODOCH_ENCRYPTION_KEYS=1:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8= \
  TODOCH_DATABASE_URL=postgresql+asyncpg://todoch:todoch@localhost:5432/todoch \
  TODOCH_REDIS_URL=memory://
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload

# Frontend – http://localhost:5173 (proxies /api to the backend)
cd frontend && npm install && npm run dev
```

| Tests | Command |
| --- | --- |
| Backend (pytest, needs PostgreSQL) | `cd backend && uv run pytest` |
| Frontend (Vitest) | `cd frontend && npm test` |
| End-to-end against the production build (Playwright) | `cd frontend && npx playwright test` |
| Screenshots for this page | `SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts` |

Publish a new version: `scripts/release.sh "Summary" "Change 1" "Change 2"`

Translations live in `frontend/src/lib/i18n/` (`de.ts`, `en.ts` – TypeScript makes sure both have
every key) and, for server messages, in `backend/app/i18n.py` (a test checks that every message has
an English version).

</details>

**Stack:** FastAPI · PostgreSQL 16 · Valkey + ARQ · SvelteKit + TypeScript + Tailwind · Caddy · Docker Compose<br>
**More:** [Architecture](docs/ARCHITECTURE.md) · [Security](docs/SECURITY.md) · [Decisions](docs/adr/) · [API (OpenAPI)](docs/openapi.json)

<div align="center">
<br>
<sub>MIT license · © 2026 MoinMornhart</sub>
</div>
