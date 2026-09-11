# ADR 0005 – Docker im LXC, Updates aus Release-Tags

**Status:** angenommen (v0.0.1)

## Kontext

Vorgabe: ein Befehl auf dem Proxmox-Host (im Stil der community-scripts), eine Konsole ohne
Passwort und ein einziger Befehl `update`, der immer die neueste Version installiert – mit
Sicherung und automatischem Rückfall.

## Entscheidung

- Unprivilegierter Debian-13-LXC mit `nesting=1,keyctl=1`, darin Docker aus dem offiziellen
  Docker-Repository und der Compose-Stack aus `deploy/docker-compose.yml`.
- Jede Version liegt unter `/opt/todoch-releases/X.Y.Z` (Quellcode des Git-Tags), `/opt/todoch`
  ist ein Link auf die aktive Version. Images werden lokal gebaut und nach Version getaggt
  (`todoch-app:X.Y.Z`), damit der Rückfall ohne Registry und ohne Neubau funktioniert.
- `update`: neueste Version über die GitHub-API ermitteln (kein CDN-Cache) → herunterladen → bauen
  (die alte Version läuft weiter) → Datenbank sichern → umschalten → Health-Check → bei Fehler Link
  zurück, Datenbank wiederherstellen, alte Version starten. Die zwei neuesten Versionen bleiben liegen.
- Geheimnisse erzeugt der Installer (`openssl rand`) in `/etc/todoch/todoch.env` (0600).
- Alle Einstellungen der Installation lassen sich per `var_*` vorgeben – auch ohne Rückfragen per SSH.

## Folgen

Das erste Bauen dauert einige Minuten (Images laden, Frontend bauen); dafür ist keine Container-
Registry nötig und jede Installation baut genau den getaggten, geprüften Quellcode.
