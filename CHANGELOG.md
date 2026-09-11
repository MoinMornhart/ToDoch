# Changelog

Alle Änderungen an Todoch – die neueste Version steht oben.
Versionsschema: `0.0.1 → 0.0.2 → … → 0.0.9 → 0.1.0 → … → 0.9.9 → 1.0.0`.
Im Container spielt der Befehl `update` immer die neueste Version ein.

## [0.1.5] – 2026-09-11

Stabilere Tests nach Streamo × ToDoch

- Ende-zu-Ende-Test sucht „Dieses Gerät“ jetzt exakt – der Hinweis „Gilt für dieses Gerät“ bei der Darstellung hatte ihn in der CI irritiert
- Git-Remote auf den neuen Repo-Namen ToDoch umgestellt

## [0.1.4] – 2026-09-11

Streamo × ToDoch: Kalender einbinden

- Neu unter Bereiche: Kalender per ICS-Adresse einbinden – z. B. Streamo mit geplanten Filmen, Sehplänen und neuen Folgen
- Abgleich automatisch im Hintergrund (alle 15 Minuten bis täglich) und auf Knopfdruck: neue Termine kommen dazu, geänderte werden aktualisiert, entfallene gelöscht
- Übernommene Termine sind in ToDoch nur lesbar (Hinweis im Termin, kein Verschieben per Drag & Drop)
- Sicherheit: Abo-Adresse verschlüsselt gespeichert, SSRF-Schutz auch bei Weiterleitungen, Heimnetz-Adressen nur für Admins, Größen- und Zeitlimits
- README: Abschnitt „Streamo × ToDoch“

## [0.1.3] – 2026-09-11

Sprachknopf neben der Suche und englische Bilder

- Neuer Knopf DE/EN neben der Suchlupe: schaltet die Sprache sofort um und speichert sie im Profil
- Englische README mit eigenen englischen Screenshots (docs/images/en)
- Deutsche Screenshots mit neuem Logo aktualisiert

## [0.1.2] – 2026-09-11

Englische Version und neues Logo – jetzt ToDoch

- README auf Englisch (README.en.md) mit Umschalter Deutsch/English oben in beiden Fassungen (closes #1)
- Sprache schon auf der Anmeldeseite umschaltbar; ohne Wahl gilt die Browsersprache, nach dem Anmelden die aus dem Profil
- Fehlermeldungen des Servers kommen jetzt auch auf Englisch – ein Test stellt sicher, dass jede Meldung übersetzt ist
- ICS-Abos zeigen „Busy“ statt „Belegt“ bei englischer Sprache
- Neuer Name ToDoch mit großem D, neues Icon: „TD“ im Hintergrund, davor ein Haken (App, Favicon, App-Icons)

## [0.1.1] – 2026-09-11

Admins ändern ihr Passwort ohne das alte

- Als Admin unter Einstellungen → Passwort ändern nur noch das neue Passwort eingeben – praktisch z. B. nach der Anmeldung per Passkey
- Normale Nutzer bestätigen weiterhin mit dem aktuellen Passwort; wer es angibt, muss das richtige nehmen
- Absicherung: Änderung meldet alle anderen Geräte ab und wird im Audit-Log vermerkt (ohne altes Passwort)

## [0.1.0] – 2026-09-11

Passkeys: Anmelden ohne Passwort

- Anmelden mit Passkey – Face ID, Touch ID, Windows Hello, Handy oder Sicherheitsschlüssel, ohne E-Mail und Passwort einzutippen
- Passkeys erscheinen auch direkt im Autofill des E-Mail-Felds
- Einstellungen → Passkeys: hinzufügen (mit Passwort-Bestätigung), umbenennen, entfernen; zeigt synchronisierte Passkeys und letzte Nutzung
- Angemeldete Geräte zeigen, ob per Passkey oder Passwort angemeldet wurde
- Sicherheit: Einmal-Challenges (kein Replay), Prüfung von Herkunft und RP-ID, Erkennung geklonter Schlüssel, Rate-Limits und Audit-Log
- „Telefontermin“ heißt jetzt „Vereinbarter Termin“ – für Termine, die am Telefon ausgemacht wurden; Ort steht standardmäßig auf „Vor Ort“

## [0.0.9] – 2026-09-11

Telefontermine – Meilenstein 3 abgeschlossen

- Neues Formular „Telefontermin“ (Taste t, Menü Neu, Übersicht): Kontakt, Termin, Vereinbarung, Notizen und Einordnung in einem Schritt
- Kontakte werden gespeichert und beim Tippen vorgeschlagen; Verwaltung unter Einstellungen → Kontakte
- Ort als telefonisch, vor Ort oder Video mit Link; eigene Zeitzone je Termin
- Folgeaufgabe (z. B. „Unterlagen vorbereiten“) X Tage vorher, mit dem Termin verknüpft – „Zum Termin“ in der Aufgabe
- Entwurf wird laufend auf dem Gerät gesichert und beim Abmelden gelöscht
- Nach dem Speichern: ICS herunterladen (ohne interne Notizen), per E-Mail senden, weiterer Termin für denselben Kontakt
- Termin-Dialog zeigt Kontakt mit Telefon- und Mail-Link, Vereinbarung und Aufgaben; jeder Termin als ICS herunterladbar
- Sicherheit: Kontakte sind privat je Nutzer (IDOR-Tests), Löschen entfernt nur die Verknüpfung

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
