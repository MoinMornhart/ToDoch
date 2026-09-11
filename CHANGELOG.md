# Changelog

Alle Änderungen an Todoch – die neueste Version steht oben.
Versionsschema: `0.0.1 → 0.0.2 → … → 0.0.9 → 0.1.0 → … → 0.9.9 → 1.0.0`.
Im Container spielt der Befehl `update` immer die neueste Version ein.

## [0.0.8] – 2026-09-11

Übersicht, Aufgaben als Ticket, Dunkelmodus und gekürzter Kalender

- Neue Startseite „Übersicht“: Begrüßung, Kennzahlen, Überfälliges, Heute, nächste Termine, Demnächst und Bereiche auf einen Blick
- Menü „Neu“ in der Seitenleiste (auf dem Handy als ➕-Knopf): Aufgabe als Ticket mit vollständigem Formular oder Termin anlegen
- Dunkelmodus: Umschalter oben rechts, unter Einstellungen → Darstellung wählbar (System, Hell, Dunkel), ohne Aufblitzen beim Laden
- Kalender je Bereich kürzen: Tage und Stunden einstellbar, z. B. Arbeit nur Mo–Fr von 8 bis 18 Uhr
- Wochen- und Tagesansicht: Kopfzeile und Raster liegen jetzt exakt übereinander
- Nach Anmeldung und Einrichtung öffnet sich die Übersicht

## [0.0.7] – 2026-09-11

Erinnerungen per Push – Meilenstein 2 (Kalender) abgeschlossen

- Terminerinnerungen als Push-Benachrichtigung auf Handy und Desktop, auch wenn die App geschlossen ist
- Unter Einstellungen pro Gerät aktivieren, Testnachricht senden, Geräte verwalten
- Serverschlüssel (VAPID) erzeugt Todoch selbst und speichert sie verschlüsselt – keine Konfiguration nötig
- Jede Erinnerung kommt genau einmal, auch bei Serien; abgemeldete Geräte werden automatisch entfernt
- Sicherheit: Push nur an bekannte Dienste (Google, Mozilla, Apple, Microsoft), Geräte-Schlüssel verschlüsselt gespeichert

## [0.0.6] – 2026-09-11

ICS-Abos für Apple, Google und Outlook

- Kalender in der Navigation jetzt bei Bereiche
- Neu unter Bereiche: geheime ICS-Abo-Links für alle oder einen Bereich, mit Detailstufe (alles, nur Titel, nur Belegt)
- Abo-Link mit einem Klick in Apple Kalender, Google Kalender oder Outlook öffnen, jederzeit einzeln widerrufbar
- Serien, Ausnahmen, geänderte Einzeltermine und Zeitzonen werden korrekt übertragen (VTIMEZONE, RRULE, EXDATE, RECURRENCE-ID)
- Abo-Links nur als Hash gespeichert, Rate-Limit, ETag-Caching; geheime Links werden aus den Caddy-Protokollen gefiltert
- CI prüft zusätzlich alle drei Caddy-Konfigurationen

## [0.0.5] – 2026-09-11

Kalender mit Terminen, Serien und Drag & Drop

- Neue Kalenderseite: Monat, Woche, Tag und Agenda, Aufgaben mit Fälligkeit direkt im Kalender
- Termine mit Ort, Link, Teilnehmern, Beschreibung, Erinnerungen, Status und Bereich; ganztägig und mehrtägig
- Wiederkehrende Termine (auch z. B. letzter Freitag im Monat) mit Bearbeiten und Löschen für nur diesen, diesen und folgende oder alle
- Termine per Drag & Drop verschieben; feste Termine fragen vorher nach
- Warnung bei Überschneidungen im selben Bereich
- Termine des Tages auf der Heute-Seite, Termine in der Suche, Tastenkürzel c, Pfeiltasten und m/w/d/a
- Zeitzonen- und sommerzeitfeste Wiederholungen, 31 Backend-Tests für Termine und ein Browser-Test für den Kalender

## [0.0.4] – 2026-09-11

Neue Projektseite mit Screenshots und schönere Oberfläche

- README neu gestaltet: Logo, Badges, Screenshots (hell/dunkel, Handy), Funktionsübersicht, ausklappbare Details
- Logo in Seitenleiste, Anmeldung und Einrichtung
- Schnellerfassung ohne doppelten Fokusrahmen, kurzer Platzhalter auf dem Handy
- Bearbeiten-Dialog öffnet beim Titel
- Screenshots per Playwright reproduzierbar (SCREENSHOTS=1)

## [0.0.3] – 2026-09-11

CI: setup-uv auf exakte Version festgelegt

- astral-sh/setup-uv@v10.1.0 statt nicht vorhandenem Sammel-Tag v10

## [0.0.2] – 2026-09-11

CI: Shell-Prüfung und aktuelle GitHub-Actions

- shellcheck-Regeln für bewusst nachgeladene Skripte und deutsche Anführungszeichen begründet abgeschaltet (.shellcheckrc)
- GitHub-Actions setup-uv v10 und upload-artifact v7 (keine Node-20-Warnung mehr)

## [0.0.1] – 2026-09-11

Neustart von Todoch: minimalistische, sicherheitsorientierte To-do-App (Meilenstein 1 – Grundgerüst)

- Neuer Technik-Stack: FastAPI (Python 3.12), PostgreSQL 16, Redis/Valkey + ARQ, SvelteKit + TypeScript + Tailwind als installierbare PWA, Caddy, Docker Compose
- Ersteinrichtung des Admin-Kontos mit einmaligem Einrichtungscode, keine Standardzugangsdaten
- Anmeldung mit Passwort (Argon2id, mind. 12 Zeichen, Abgleich mit Leak-Liste), serverseitige Sitzungen mit Idle- und Absolut-Timeout, Geräteübersicht, „Überall abmelden“
- Schutz gegen CSRF (Double-Submit + Origin-Prüfung), Rate-Limits mit exponentiellem Backoff, strenge Security-Header und CSP ohne 'unsafe-inline', unveränderliches Audit-Log
- Bereiche (Arbeit, Privat und eigene) mit Farbe und Symbol, Bereichsfilter für alle Ansichten
- Aufgaben mit Notiz (Markdown, serverseitig bereinigt), Fälligkeit, Priorität, Tags, Unterpunkten und Wiederholungen
- Ansichten Heute, Demnächst, Alle offen, Erledigt und Tagesansicht, Volltextsuche
- Schnellerfassung in natürlicher Sprache, z. B. „Rechnung zahlen morgen 14:00 !hoch #finanzen @arbeit“
- Tastaturbedienung: n, /, j, k, x, e, ?; Deutsch und Englisch, Hell- und Dunkelmodus
- Proxmox-Quickstart im Stil der community-scripts (Docker im LXC), Befehle `update` und `todoch`, Sicherung vor jedem Update mit automatischem Rückfall
