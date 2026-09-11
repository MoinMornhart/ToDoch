#!/usr/bin/env bash
# Neue Todoch-Version veröffentlichen.
#
# Versionsschema: 0.0.1 → 0.0.2 → … → 0.0.9 → 0.1.0 → … → 0.9.9 → 1.0.0
# Aufruf:  scripts/release.sh "Kurzbeschreibung" "Änderung 1" "Änderung 2" …
#
# Erhöht die Version (VERSION, backend/pyproject.toml, backend/uv.lock, frontend/package*.json),
# trägt die Änderungen in CHANGELOG.md ein, committet mit beschreibender Nachricht, setzt das
# Tag vX.Y.Z, pusht und legt (mit angemeldeter GitHub-CLI) ein GitHub-Release an.
# Danach holt sich jeder Server mit dem Befehl „update“ diese Version.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -lt 1 ]]; then
  echo "Aufruf: $0 \"Kurzbeschreibung\" [\"Änderung\" …]" >&2
  exit 1
fi
if [[ -n "$(git status --porcelain --untracked-files=no -- VERSION CHANGELOG.md)" ]]; then
  echo "VERSION oder CHANGELOG.md haben uncommittete Änderungen." >&2
  exit 1
fi
SUMMARY=$1
shift

CURRENT=$(tr -d '[:space:]' <VERSION)
IFS=. read -r MAJOR MINOR PATCH <<<"$CURRENT"
PATCH=$((PATCH + 1))
if ((PATCH > 9)); then
  PATCH=0
  MINOR=$((MINOR + 1))
fi
if ((MINOR > 9)); then
  MINOR=0
  MAJOR=$((MAJOR + 1))
fi
NEXT="${MAJOR}.${MINOR}.${PATCH}"
echo "Version: ${CURRENT} → ${NEXT}"

echo "$NEXT" >VERSION
# Erste version-Zeile in pyproject.toml, Paketeintrag „todoch“ in uv.lock
sed -i -E "0,/^version = \".*\"/s//version = \"${NEXT}\"/" backend/pyproject.toml
awk -v v="$NEXT" 'f && /^version = / { $0 = "version = \"" v "\""; f = 0 } /^name = "todoch"$/ { f = 1 } { print }' \
  backend/uv.lock >backend/uv.lock.tmp && mv backend/uv.lock.tmp backend/uv.lock
# package.json: erste „version“; package-lock.json: Wurzel und packages[""]
for f in frontend/package.json frontend/package-lock.json; do
  limit=1
  [[ "$f" == *lock.json ]] && limit=2
  awk -v v="$NEXT" -v max="$limit" 'n < max && /"version": "/ { sub(/"version": "[^"]+"/, "\"version\": \"" v "\""); n++ } { print }' \
    "$f" >"$f.tmp" && mv "$f.tmp" "$f"
done

ITEMS=""
for item in "$@"; do ITEMS+="- ${item}"$'\n'; done
ENTRY="## [${NEXT}] – $(date +%F)"$'\n\n'"${SUMMARY}"$'\n'
[[ -n "$ITEMS" ]] && ENTRY+=$'\n'"${ITEMS}"
ENTRY="$ENTRY" awk '!done && /^## / { print ENVIRON["ENTRY"]; done = 1 } { print } END { if (!done) print ENVIRON["ENTRY"] }' \
  CHANGELOG.md >CHANGELOG.md.tmp && mv CHANGELOG.md.tmp CHANGELOG.md

BODY="${ITEMS}"
[[ -n "${RELEASE_TRAILER:-}" ]] && BODY+=$'\n'"${RELEASE_TRAILER}"
COMMIT_ARGS=(-q -m "v${NEXT}: ${SUMMARY}")
[[ -n "$BODY" ]] && COMMIT_ARGS+=(-m "$BODY")

git add -A
git commit "${COMMIT_ARGS[@]}"
git tag -a "v${NEXT}" -m "v${NEXT}: ${SUMMARY}"
git push -q origin HEAD --follow-tags

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh release create "v${NEXT}" --title "v${NEXT} – ${SUMMARY}" --notes "${SUMMARY}"$'\n\n'"${ITEMS}" >/dev/null &&
    echo "GitHub-Release v${NEXT} erstellt."
fi
echo "✔ v${NEXT} veröffentlicht. Server aktualisieren mit: update"
