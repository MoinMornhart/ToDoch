# ADR 0004 – Serverseitige Sitzungen und CSRF-Schutz

**Status:** angenommen (v0.0.1)

## Entscheidung

- **Sitzungen** liegen in PostgreSQL (`user_sessions`), im Cookie steht nur ein zufälliges Token
  (256 Bit), gespeichert wird dessen SHA-256. Damit sind Sitzungen einzeln widerrufbar, in der
  Oberfläche mit Gerät/IP/Zeit sichtbar, und ein Datenbank-Leak liefert keine gültigen Tokens.
- **Cookies:** `__Host-todoch_session` (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`) und
  `__Host-todoch_csrf` (lesbar für die Oberfläche). Das Präfix `__Host-` verhindert, dass
  Subdomains die Cookies setzen oder überschreiben (Cookie-Tossing).
- **CSRF:** Jede zustandsändernde Anfrage an `/api` braucht (1) eine passende `Origin` (bzw.
  `Referer`) **und** (2) den Wert des CSRF-Cookies im Header `X-CSRF-Token`. Das Token wird bei
  Anmeldung, Abmeldung und Passwortwechsel erneuert. Umgesetzt als ASGI-Middleware, damit keine
  Route es vergessen kann; Ausnahmen (z. B. künftige CalDAV-Endpunkte mit Basic-Auth) werden
  explizit gelistet.
- **Timeouts:** Idle (Standard 12 h) und absolut (Standard 7 Tage), beide konfigurierbar.

## Alternativen

JWTs wurden verworfen: nicht einzeln widerrufbar ohne serverseitige Sperrliste – dann ist eine
Sitzungstabelle einfacher und sicherer.
