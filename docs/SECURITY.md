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
| **Bösartige E-Mail** | Tracking, Skriptausführung, ReDoS, SSRF, Speicher-DoS | HTML aus Mails wird nie gerendert, sondern serverseitig zu Text (nh3); Größen-, Anzahl- und Zeitlimits beim Abholen; SSRF-Schutz für Mailserver, Kalender-Abos und CalDAV – verbunden wird immer genau mit der geprüften IP |
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

## Audit-Log: IP-Adressen nur 90 Tage (seit v0.3.6)

Das Audit-Log ist weiter nur anhängbar – mit genau einer Ausnahme, die die Datenbank selbst prüft:
Bei Einträgen, die älter als 90 Tage sind, darf die IP-Adresse entfernt werden, sonst nichts. Ein
täglicher Job erledigt das. Ereignis, Zeitpunkt und pseudonyme Nutzer-ID bleiben, auch nach dem
Löschen eines Kontos; eine übernommene App kann frische Einträge weiterhin nicht verändern.

## Review nach OWASP ASVS 4.0.3 Level 2 (v0.3.1–v0.3.6)

Der Code wurde Kapitel für Kapitel gegen ASVS L2 geprüft. Alle belegten Funde sind behoben:

| Fund | ASVS | Behoben in |
| --- | --- | --- |
| DNS-Rebinding bei Kalender-Abos und CalDAV (SSRF) | V12.6.1, V5.2.6 | v0.3.2 |
| 100.64.0.0/10 (CGNAT, NetBird, Tailscale) für Nicht-Admins erreichbar | V12.6.1 | v0.3.2 |
| Client-IP über `X-Forwarded-For` fälschbar (Rate-Limits, Audit-Log) | V2.2.1, V7.1.4 | v0.3.3 |
| Admins ändern ihr Passwort ohne das alte | V2.1.6, V3.7.1 | v0.3.4 |
| Passkeys ohne erzwungene Gerätesperre, trotzdem als zweiter Faktor | V2.2 (AAL2) | v0.3.4 |
| Falscher Code beim Kontolöschen nicht im Audit-Log | V7.1.3 | v0.3.4 |
| Service Worker hielt Mails und Sitzungen offline vor | V8.2.1, V8.2.3 | v0.3.5 |
| `update` fiel ohne Tag still auf `main` zurück | V10.3.2 | v0.3.5 |
| CA-Zertifikat per HTTP ohne Vergleichsmöglichkeit | V9.1 | v0.3.5 |
| IP-Adressen im Audit-Log ohne Löschfrist | V8.3.8 | v0.3.6 |

**Bewusste Abweichung:** Sitzungen laufen nach 12 Stunden ohne Nutzung bzw. spätestens nach 7 Tagen
ab (ASVS L2: 30 Minuten bzw. 12 Stunden). Für eine selbst gehostete To-do-App im eigenen Netz wiegt
das tägliche Neuanmelden schwerer; beide Werte sind per `.env` einstellbar, jede Sitzung ist einzeln
widerrufbar, und „Überall abmelden“ beendet alle.

**Erfüllt** (Stichproben im Code): V1.1 Bedrohungsmodell · V2.1 Passwortregeln (≥ 12 Zeichen,
Leak-Liste, keine Kompositionsregeln) · V2.4 Argon2id · V2.8 TOTP mit Replay-Schutz · V2.10 keine
fest eingebauten Zugangsdaten · V3.2/V3.4 Sitzungs-Token und Cookies · V3.3 Abmelden, Widerruf ·
V4.1/V4.2 zentrale Autorisierung, 404 für Fremdes, CSRF doppelt geprüft · V5.3 Ausgabe escaped,
nur ORM-Abfragen · V5.5 defusedxml · V6.2/V6.4 AES-256-GCM, Schlüssel getrennt · V7.1.1 keine
Geheimnisse in Logs · V8.3 Export und Löschen · V9 TLS und HSTS · V12.1 Größenlimits · V13.1
OpenAPI im Betrieb aus · V14.4 Security-Header und CSP · V14.5 kein CORS · gehärtete Container.

**Nicht zutreffend:** V2.5 Passwort-Reset per Mail (nur `todoch reset-password` in der Konsole) ·
V3.5 JWT · V12.2–12.5 Datei-Uploads · V13.4 GraphQL · V4.3.1 Admin-Weboberfläche (Verwaltung nur in
der Konsole).

## Gerät, Updates und Zertifikat (seit v0.3.5)

- **Offline-Speicher im Browser:** Der Service Worker legt nur Aufgaben, Termine, Bereiche und den
  Anmeldestand ab – nie Mails, Konto, Sitzungen, Passkeys, Zwei-Faktor oder Einladungen. Beim An-
  und Abmelden und sobald der Server eine abgelaufene Sitzung meldet (401, auch nach „Überall
  abmelden“ von einem anderen Gerät), wird der Speicher gelöscht; der ältere, weiter gefasste
  Speicher früherer Versionen wird beim Aktualisieren entfernt.
- **Updates:** `update` lädt ausschließlich den Tag der neuen Version. Früher sprang es ohne Tag
  still auf den aktuellen Stand von `main` – das ist entfernt. Bleibendes Restrisiko: Wer das
  GitHub-Konto übernimmt, kann Versionen veröffentlichen; signierte Releases sind geplant.
- **ToDoch-CA:** Das Stammzertifikat kommt im Heimnetz per HTTP (`/ca.crt`), damit Geräte es ohne
  Warnung laden können. `todoch info` zeigt seinen SHA-256-Fingerabdruck – vor dem Installieren
  vergleichen, dann fällt ein Austausch im LAN auf.

## Anmeldung nachgeschärft (seit v0.3.4)

- **Passkeys nur mit Gerätesperre:** Registrierung und Anmeldung verlangen Benutzerverifikation
  (Fingerabdruck, Gesicht, PIN – `userVerification: required`, serverseitig geprüft). Ein Passkey
  ersetzt den zweiten Faktor; ein gestohlener Sicherheitsschlüssel ohne PIN reicht dafür nicht.
- **Passwort ändern** geht nur mit dem aktuellen Passwort – ohne nur in den ersten zehn Minuten nach
  einer Anmeldung per Passkey. Früher durften Admins immer ohne; eine übernommene Sitzung hätte so
  Passwort und danach Passkey austauschen und den echten Admin aussperren können.
- Ein falscher Zwei-Faktor-Code beim Löschen des Kontos landet im Audit-Log
  (`account.delete_failed`).

## Echte Client-IP (seit v0.3.3)

Rate-Limits je IP (Anmeldung, Zwei-Faktor, Passkeys, Einrichtung, Feeds), Audit-Log und
Sitzungsliste hängen an der Client-IP. Caddy gibt der App genau eine IP weiter – die, die Caddy
selbst für den Client hält (`header_up X-Forwarded-For {client_ip}`); was ein Client selbst in
`X-Forwarded-For` schreibt, kommt nie durch.

- **internal / acme:** Kein Proxy davor, Caddy vertraut niemandem – zählt nur die echte Adresse.
- **proxy:** Nur Absender aus `TODOCH_TRUSTED_PROXIES` dürfen die Client-IP mitteilen, gelesen wird
  von rechts (`trusted_proxies_strict`) – vorangestellte, gefälschte Einträge zählen nicht.
  Standard ist „privates Netz“, damit NetBird, NPM & Co. ohne Einrichtung funktionieren. Wer im
  Heimnetz auch Geräten misstraut, legt die Adresse des Proxys fest: `todoch proxy-ip <IP>`.

## Adressen von Nutzern: geprüft und festgenagelt (seit v0.3.2)

Kalender-Abos, CalDAV und Online-Kalender verbinden sich über ein eigenes Netzwerk-Backend
(`PinnedBackend` in `services/external_calendars.py`): Der Name wird beim Verbinden aufgelöst,
jede IP geprüft und genau mit dieser IP verbunden – TLS-Zertifikat und SNI gelten weiter für den
Namen. Ein Server, der bei der Prüfung eine öffentliche und beim Verbinden eine interne Adresse
nennt (DNS-Rebinding), kommt so nicht mehr ins Heimnetz, an Loopback oder ins Docker-Netz. Für
Postfächer gilt das schon seit v0.2.1.

Wer kein Admin ist, erreicht nur öffentliche Adressen (`is_global`). Gesperrt sind damit auch
100.64.0.0/10 (CGNAT, NetBird, Tailscale), die Python nicht als „privat“ zählt. Admins dürfen ins
eigene Netz (z. B. Streamo oder Nextcloud im Heimnetz), Loopback, Link-Local und Cloud-Metadaten
bleiben auch für sie gesperrt.

Mail-Regeln vergleichen nur Text (kein regulärer Ausdruck) – ReDoS ist dort nicht möglich.

## Getestete Wiederherstellung (seit v0.3.1)

Eine Sicherung zählt erst, wenn sie sich zurückspielen lässt. `scripts/restore-test.sh` läuft bei
jedem Push in der CI: Es startet ToDoch mit Docker Compose, legt ein Konto an, sichert mit denselben
Funktionen wie `todoch backup`, löscht die Daten, spielt die Sicherung wie `todoch restore` zurück
und prüft Konto, Datenbank-Stand und Start. Außerdem wird kontrolliert, dass die Schlüssel getrennt
unter `keys/` neben der Sicherung liegen.

## Offene Punkte (geplant)

- Kürzere Sitzungs-Standardwerte, nachdem Passkeys und Zwei-Faktor verbreitet genutzt werden.
- Falls Datei-Anhänge kommen: Prüfung per Magic Bytes, Ablage außerhalb des Webroots (bisher gibt
  es keine Uploads).
- Signierte Releases, die der Container vor dem Update prüft.

## Datenexport und Kontolöschung (seit v0.3.0)

Unter *Einstellungen → Konto* lädt „Daten exportieren“ alle eigenen Daten als JSON (DSGVO Art. 15
und 20). Spalten mit Passwörtern, Geheimnissen, Tokens, Hashes oder verschlüsselten Zugangsdaten
kommen grundsätzlich nicht in die Datei – ein Test prüft das. „Konto löschen“ (Art. 17) verlangt
das Passwort und, falls eingerichtet, einen Zwei-Faktor- oder Wiederherstellungscode; das letzte
Admin-Konto lässt sich nicht löschen. Alles Eigene verschwindet per Datenbank-Kaskade; Aufgaben
und Kommentare in Bereichen anderer bleiben ohne Namen erhalten. Das Audit-Log behält nur die
pseudonyme Nutzer-ID (kein Fremdschlüssel, nur anhängbar).
