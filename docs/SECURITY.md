# Sicherheit

Todoch speichert private Termine, Aufgaben und später Zugangsdaten zu E-Mail-Konten. Sicherheit
geht deshalb vor Komfort: sichere Voreinstellungen, nichts Sicherheitsrelevantes ist abschaltbar
(Ausnahme: Passkeys sind freiwillig, ein Passwort bleibt immer als Rückfall).

Sicherheitslücken bitte vertraulich über „Security → Report a vulnerability“ im GitHub-Repository
melden, nicht als öffentliches Issue.

## Bedrohungsmodell

| Angreifer | Ziel | Gegenmaßnahmen |
| --- | --- | --- |
| **Im LAN** (fremdes Gerät im WLAN, kompromittiertes IoT-Gerät) | Anmeldung erraten, Verkehr mitlesen, Setup kapern | HTTPS mit HSTS in allen Betriebsarten; Ersteinrichtung nur mit Einmalcode; Rate-Limits und exponentielles Backoff pro Konto und IP; generische Fehlermeldungen; Datenbank und Redis nur im internen Docker-Netz ohne Ports |
| **Gestohlenes Backup** | Zugangsdaten und Inhalte auslesen | Passwörter nur als Argon2id-Hash; Mail-Passwörter/OAuth-Tokens (ab M4/M5) mit AES-256-GCM verschlüsselt, Schlüssel liegt **nicht** in der Datenbank und nicht im Backup-Archiv, sondern getrennt (`keys/`) |
| **Kompromittierter Browser / XSS** | Sitzung übernehmen, Daten abgreifen | Sitzungscookie `HttpOnly`, `Secure`, `SameSite=Lax`, Präfix `__Host-`; strenge CSP ohne `'unsafe-inline'` (Skripte nur aus eigenen Dateien); Markdown serverseitig per Allowlist bereinigt; Sitzungen einzeln widerrufbar, „Überall abmelden“ |
| **Fremde Website (CSRF)** | Aktionen im Namen des Nutzers auslösen | Double-Submit-Token (`__Host-todoch_csrf` + Header `X-CSRF-Token`) **und** Origin-/Referer-Prüfung für jede zustandsändernde Anfrage; `SameSite=Lax` |
| **Bösartige E-Mail** (ab M4) | Tracking, Skriptausführung, ReDoS, SSRF, Zip-/XML-Bomben | HTML aus Mails nie direkt rendern; Regex mit Timeout; Größen- und Zeitlimits in Worker-Jobs; SSRF-Schutz für Autoconfig/CalDAV |
| **Andere Nutzer derselben Instanz** | Fremde Daten sehen oder ändern (IDOR) | Zentrale Autorisierung `can(user, action, obj)`; jede Abfrage filtert serverseitig; nicht sichtbare Objekte ergeben 404; automatisierte Tests prüfen **jede** Route mit Objekt-ID gegen Fremdzugriff |

## Umgesetzte Maßnahmen (Stand v0.0.1)

**Authentifizierung und Sitzungen**
- Passwörter: Argon2id (RFC 9106, 64 MiB, t=3, p=4), mindestens 12 Zeichen, Abgleich gegen eine
  Offline-Liste bekannter Leak-Passwörter (nur 8-Byte-SHA-1-Präfixe, keine Klartexte), darf weder
  Name noch E-Mail enthalten. Parallele Hash-Berechnungen sind begrenzt (Schutz vor Speicher-DoS).
- Gleiche Rechenzeit für unbekannte Konten (keine Nutzer-Enumeration per Timing).
- Sitzungen serverseitig in der Datenbank (nur SHA-256 des Tokens gespeichert), Rotation bei
  Anmeldung und Passwortwechsel, Idle-Timeout (Standard 12 h) und absolutes Timeout (Standard 7 Tage).
  OWASP ASVS L2 empfiehlt kürzere Werte; beide sind per `.env` einstellbar. Mit Passkeys (M6) ist die
  erneute Anmeldung ein Fingertipp – dann werden die Standardwerte gesenkt.
- Passwortwechsel beendet alle anderen Sitzungen.

**Anfragen**
- Größenlimit für Anfragen (Standard 1 MB, geprüft per `Content-Length` und beim Lesen).
- Strikte Validierung aller Eingaben (Pydantic), Längenlimits für alle Felder.
- Ausschließlich parametrisierte Abfragen über das ORM; die Volltextsuche erlaubt nur Wortzeichen.
- Validierungsfehler spiegeln Eingaben nie zurück (keine Passwörter in Fehlermeldungen).

**Header** (API und Oberfläche): `Content-Security-Policy` (Oberfläche: `default-src 'self'`,
`script-src 'self'`, `style-src 'self'`, `frame-ancestors 'none'` …; API: `default-src 'none'`),
`Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`,
`Permissions-Policy`, `Cache-Control: no-store` für die API. Die E2E-Tests schlagen fehl, sobald der
Browser einen CSP-Verstoß meldet.

**Betrieb**
- Container ohne Root-Rechte (App/Worker als UID 10001), schreibgeschütztes Dateisystem,
  `no-new-privileges`, alle Capabilities entzogen (Caddy nur `NET_BIND_SERVICE`), Speicherlimits.
- Datenbank und Redis ohne veröffentlichte Ports in einem internen Netz ohne Internetzugang.
- Start bricht ab, wenn Geheimnisse fehlen, zu kurz sind oder Platzhalter enthalten; `memory://`
  als Redis-Ersatz ist im Betrieb verboten; `TODOCH_ORIGIN` muss `https://` sein.
- Keine Geheimnisse in Logs, Git oder Images (`.env` ist in `.gitignore` und `.dockerignore`).
  Zugriffslogs schreibt nur Caddy; die API protokolliert keine Anfragen.
- Audit-Log für Anmeldung, Fehlversuche, Abmeldung, Sitzungsende, Passwortwechsel und
  Verwaltungsbefehle. Die Tabelle ist per Datenbank-Trigger nur anhängbar (kein UPDATE, DELETE,
  TRUNCATE) und speichert keine Inhalte oder Geheimnisse.
- Abhängigkeits-Scans (`pip-audit`, `npm audit`), Linting, Typprüfung und Tests in der CI.

## Schlüsselrotation

`TODOCH_ENCRYPTION_KEYS` enthält einen oder mehrere Schlüssel (`1:<base64>,2:<base64>`). Neue
Chiffrate nutzen den höchsten (oder `TODOCH_ENCRYPTION_KEY_ACTIVE`). Zum Rotieren einen neuen
Schlüssel anhängen, neu starten und anschließend alle Chiffrate umschlüsseln (Befehl folgt mit
Meilenstein 4, sobald verschlüsselte Zugangsdaten gespeichert werden). Danach kann der alte
Schlüssel entfernt werden. Jedes Chiffrat enthält die Schlüssel-ID und ist per AAD an sein Feld
gebunden (kein Umkopieren zwischen Datensätzen möglich).

## Offene Punkte (geplant)

- Passkeys, TOTP und Wiederherstellungscodes (M6).
- Upload-Prüfung per Magic Bytes, Anhänge außerhalb des Webroots (M3).
- SSRF-Schutz, ReDoS-Timeouts, Härtung des ICS-Parsers (M4/M5).
- Datenexport und Kontolöschung (DSGVO), getesteter Restore in der CI, Review nach OWASP ASVS L2 (M8).
