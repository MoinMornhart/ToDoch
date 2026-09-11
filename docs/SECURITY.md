# Sicherheit

ToDoch speichert private Termine, Aufgaben und später Zugangsdaten zu E-Mail-Konten. Sicherheit
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
| **Bösartige E-Mail** | Tracking, Skriptausführung, ReDoS, SSRF, Speicher-DoS | HTML aus Mails wird nie gerendert, sondern serverseitig zu Text (nh3); Größen-, Anzahl- und Zeitlimits beim Abholen; SSRF-Schutz für Mailserver, Kalender-Abos und später CalDAV |
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

**Passkeys (WebAuthn, seit v0.1.0)**
- Anmeldung ohne Benutzernamen über „discoverable credentials“ (`residentKey: required`,
  `userVerification: preferred`); geprüft mit py_webauthn gegen RP-ID und Origin aus `TODOCH_ORIGIN`.
- Challenges liegen fünf Minuten in Redis und werden beim Prüfen gelöscht – jede gilt genau einmal
  (kein Replay). Registrierungs-Challenges sind an die Sitzung gebunden.
- Ein neuer Passkey braucht das aktuelle Passwort – eine übernommene Sitzung reicht nicht, um sich
  dauerhaft Zugang zu verschaffen.
- Der Signaturzähler darf nicht zurückspringen (Erkennung geklonter Schlüssel); das `userHandle`
  muss zum Konto passen. Fehlschläge sind rate-limitiert und landen im Audit-Log, Hinzufügen und
  Entfernen ebenfalls.
- Gespeichert werden nur öffentliche Schlüssel. Das Passwort bleibt als Rückfall bestehen.
- Tests prüfen den kompletten Ablauf mit einem Software-Authenticator (echte ES256-Signaturen) und
  im Browser mit Chromiums virtuellem Authenticator.

**Zwei-Faktor (TOTP, seit v0.1.9)**
- Optional je Konto: 6-stellige Codes nach RFC 6238 (30 s, ±1 Schritt Toleranz). Das Geheimnis
  liegt AES-256-GCM-verschlüsselt in der Datenbank, während der Einrichtung nur verschlüsselt und
  zehn Minuten lang in Redis (an die Sitzung gebunden).
- Jeder Zeitschritt gilt nur einmal (Replay-Schutz). Nach dem Passwort gibt es statt einer Sitzung
  ein fünf Minuten gültiges Einmal-Token; höchstens fünf Versuche je Token, zehn je Konto in zehn
  Minuten.
- Zehn Wiederherstellungscodes, nur als SHA-256 gespeichert, je einmal gültig. Einrichten,
  Abschalten (Passwort + Code) und neue Codes stehen im Audit-Log.
- Anmeldung per Passkey braucht keinen zweiten Faktor (Besitz + Gerätesperre). Notfall im Container:
  `todoch disable-2fa <e-mail>`.

**E-Mail-Postfächer (IMAP, seit v0.2.1)**
- Nur verschlüsselt: IMAPS oder STARTTLS (vor der Anmeldung), mindestens TLS 1.2, Zertifikat und
  Hostname werden geprüft. Unverschlüsseltes IMAP ist nicht wählbar.
- SSRF-Schutz wie bei Kalender-Abos: Der Servername wird aufgelöst und geprüft (kein Loopback, keine
  Link-Local-/Cloud-Metadaten-Adressen, Heimnetz nur für Admins); verbunden wird genau mit der
  geprüften IP, das Zertifikat gilt weiter für den Namen (kein DNS-Rebinding).
- Das Postfach-Passwort wird erst nach erfolgreicher Anmeldung gespeichert, AES-256-GCM-verschlüsselt
  und an das Konto gebunden (AAD); die API gibt es nie zurück. Hinzufügen, Entfernen und Passwort-
  wechsel stehen im Audit-Log.
- Nur lesend: Ordner wird schreibgeschützt ausgewählt, Inhalte per `BODY.PEEK` geholt (nichts wird
  als gelesen markiert, gelöscht oder verschoben).
- Limits: höchstens 512 KB je Mail, 200 Mails je Abgleich, 2000 gespeicherte Mails je Postfach,
  20 s Zeitlimit je Verbindung. Kaputte Mails werden übersprungen.
- Anzeige nur als Text: HTML wird mit nh3 ohne erlaubte Tags bereinigt (Skripte und Styles samt
  Inhalt entfernt), Bilder und Links werden nie geladen; Svelte gibt den Text escaped aus.
- Mails anderer Nutzer sind wie nicht vorhanden (404) – auch dafür prüfen die Autorisierungstests
  jede Route.

**Mit Google/Microsoft verbinden (OAuth 2.0, seit v0.2.4)**
- Authorization-Code-Flow mit PKCE (S256). Der `state` ist zufällig, zehn Minuten gültig, gilt genau
  einmal (Redis `GETDEL`) und ist an Nutzer und Anbieter gebunden – ein fremder oder wiederholter
  Rücksprung wird verworfen.
- Die Adressen der Anbieter sind fest eingebaut (kein SSRF); Client-ID und Secret stehen nur in der
  Server-Konfiguration (`todoch oauth …`), nie in der Datenbank oder im Browser.
- Gespeichert wird nur das Refresh-Token, AES-256-GCM-verschlüsselt wie ein Postfach-Passwort;
  Zugriffstoken leben nur für einen Abgleich im Speicher. Erneuert der Anbieter das Refresh-Token,
  wird das neue gespeichert. Die IMAP-Anmeldung läuft per XOAUTH2 über TLS.
- Die E-Mail-Adresse kommt aus dem ID-Token, das ToDoch direkt per TLS vom Token-Endpunkt erhält
  (OpenID Connect Core 3.1.3.7).

**Scheitert die Anmeldung beim Anbieter (seit v0.2.6)**, zeigt ToDoch den Fehlercode des Anbieters
(z. B. `invalid_client`) und schreibt die Beschreibung ins Protokoll – nie Client-Secret, Code oder
Tokens.

**Outlook-Kalender (Microsoft Graph, seit v0.2.6)**: nur Recht auf Termine
(`Calendars.ReadWrite`), nur Aufrufe an `graph.microsoft.com`; Folgeseiten der Liste werden nur
geladen, wenn sie ebenfalls dort liegen (kein SSRF über `@odata.nextLink`).

**Geteilte Bereiche (seit v0.2.8)**: Rollen Besitzer, Admin, Mitglied, Nur lesen – geprüft
ausschließlich über `app/policy.py`; Mitgliedschaften werden je Anfrage frisch geladen, entzogene
Rechte gelten also sofort. Einladungen sind Links mit 256 Bit Zufall hinter `#` (landet nie in
Server-Protokollen), gespeichert wird nur der SHA-256; ein Link gilt einmal und 7 Tage und wird
im Body statt in der Adresse an den Server geschickt. Es gibt keine Suche nach Konten per E-Mail
(keine Konto-Enumeration). Löschen kann nur der Besitzer; die Autorisierungstests prüfen auch
Mitglieder- und Einladungs-Routen gegen Fremdzugriff. Zuständig kann nur sein, wer im Bereich
schreiben darf (wird serverseitig geprüft, beim Verschieben in einen anderen Bereich erneut).
Kommentare werden wie Notizen per Allowlist bereinigt angezeigt; schreiben darf, wer die Aufgabe
ändern darf, fremde Kommentare löschen nur Admins und Besitzer (seit v0.2.9).

**CalDAV (Nextcloud, iCloud & Co., seit v0.2.7)**: Benutzername und App-Passwort werden erst
nach einem erfolgreichen Abruf gespeichert, das Passwort AES-256-GCM-verschlüsselt und nie
ausgegeben. Jede Adresse – auch nach Weiterleitungen – wird wie bei Kalender-Abos geprüft
(kein Loopback, keine Cloud-Metadaten, Heimnetz nur für Admins); unverschlüsseltes `http://` nur
im eigenen Netz. XML-Antworten liest ToDoch mit defusedxml (keine Entity-Bomben, kein XXE),
höchstens 5 MB je Antwort.

**Google Kalender abgleichen (seit v0.2.5)**
- Eigene Zustimmung nur für Termine (`calendar.events`), getrennt vom Postfach; dasselbe
  State-/PKCE-Verfahren und derselbe Rücksprung. Der Bereich steht im State und wird beim
  Rücksprung erneut gegen die Rechte des Nutzers geprüft.
- Nur die feste Google-API-Adresse wird angesprochen; Refresh-Token verschlüsselt wie oben.
- Übernommene Texte werden wie alle Beschreibungen serverseitig per Allowlist bereinigt angezeigt.
- Gelöschte Termine hinterlassen einen Grabstein (nur die ID beim Anbieter), bis die Löschung bei
  Google angekommen ist.

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

- Kürzere Sitzungs-Standardwerte, nachdem Passkeys und Zwei-Faktor verbreitet genutzt werden.
- Upload-Prüfung per Magic Bytes, Anhänge außerhalb des Webroots (M3).
- ReDoS-Timeouts für Mail-Regeln, SSRF-Schutz für CalDAV (M4/M5).
- Datenexport und Kontolöschung (DSGVO), getesteter Restore in der CI, Review nach OWASP ASVS L2 (M8).
