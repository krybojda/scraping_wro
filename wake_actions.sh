#!/bin/bash
set -euo pipefail

# Uzycie:
#   MY_TOKEN=... ./wake_actions.sh
# Opcjonalnie nadpisz:
#   OWNER=krybojda REPO=scr-wro WORKFLOW_FILE=combo-scraper.yml REF=main ./wake_actions.sh

# Opcjonalnie: wklej token na stale (mniej bezpieczne).
HARDCODED_TOKEN="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"

TOKEN="${HARDCODED_TOKEN:-${MY_TOKEN:-${GITHUB_TOKEN:-${TOKEN:-}}}}"
OWNER="${OWNER:-krybojda}"
REPO="${REPO:-scr-wro}"
WORKFLOW_FILE="${WORKFLOW_FILE:-combo-scraper.yml}"
REF="${REF:-main}"

if [ -z "$TOKEN" ]; then
  echo "BLAD: brak tokena. Ustaw MY_TOKEN (lub GITHUB_TOKEN/TOKEN)."
  exit 1
fi

API_URL="https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches"

TMP_BODY="$(mktemp)"
trap 'rm -f "$TMP_BODY"' EXIT

HTTP_CODE="$(curl -sS -o "$TMP_BODY" -w "%{http_code}" -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "$API_URL" \
  -d "{\"ref\":\"$REF\"}")"

if [ "$HTTP_CODE" = "204" ]; then
  echo "OK: wyslano sygnal do GitHuba (${OWNER}/${REPO}, workflow=${WORKFLOW_FILE}, ref=${REF})."
  exit 0
fi

echo "BLAD: GitHub API zwrocilo HTTP $HTTP_CODE"
cat "$TMP_BODY"
echo

if [ "$HTTP_CODE" = "404" ]; then
  echo "Wskazowka: sprawdz OWNER/REPO/WORKFLOW_FILE oraz czy workflow istnieje na branchu '$REF'."
fi

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
  echo "Wskazowka: sprawdz token i uprawnienia (repo + workflow)."
fi

exit 1
