#!/bin/bash
set -euo pipefail

# Uzycie:
#   MY_TOKEN=... ./wake_actions.sh
# Opcjonalnie (workflow moze byc na innym koncie/repo):
#   TARGET_OWNER=inne_konto TARGET_REPO=inne_repo TARGET_WORKFLOW_FILE=combo-scraper.yml TARGET_REF=main ./wake_actions.sh
# Opcjonalnie dispatch po ID zamiast po nazwie pliku:
#   TARGET_WORKFLOW_ID=123456789 ./wake_actions.sh

# TRYB "odpalam tylko ./wake_actions.sh":
# Ustaw raz ponizsze wartosci i potem uruchamiaj samym ./wake_actions.sh
HARDCODED_TOKEN=""
DEFAULT_OWNER="krybojda"
DEFAULT_REPO="scr-wro"
DEFAULT_WORKFLOW_FILE="combo-scraper.yml"
DEFAULT_REF="main"

TOKEN="${HARDCODED_TOKEN:-${MY_TOKEN:-${GITHUB_TOKEN:-${TOKEN:-}}}}"
OWNER="${TARGET_OWNER:-${OWNER:-${DEFAULT_OWNER}}}"
REPO="${TARGET_REPO:-${REPO:-${DEFAULT_REPO}}}"
WORKFLOW_FILE="${TARGET_WORKFLOW_FILE:-${WORKFLOW_FILE:-${DEFAULT_WORKFLOW_FILE}}}"
WORKFLOW_ID="${TARGET_WORKFLOW_ID:-${WORKFLOW_ID:-}}"
REF="${TARGET_REF:-${REF:-${DEFAULT_REF}}}"

if [ -z "$TOKEN" ]; then
  echo "BLAD: brak tokena. Ustaw MY_TOKEN (lub GITHUB_TOKEN/TOKEN)."
  exit 1
fi

AUTH_HEADERS=(
  -H "Accept: application/vnd.github+json"
  -H "Authorization: Bearer $TOKEN"
  -H "X-GitHub-Api-Version: 2022-11-28"
)

REPO_API="https://api.github.com/repos/${OWNER}/${REPO}"
WORKFLOWS_API="${REPO_API}/actions/workflows"

echo "Cel dispatch: ${OWNER}/${REPO}, workflow=${WORKFLOW_FILE}, ref=${REF}"

TMP_BODY="$(mktemp)"
TMP_WORKFLOWS="$(mktemp)"
trap 'rm -f "$TMP_BODY" "$TMP_WORKFLOWS"' EXIT

# 1) Szybki check dostepu do repo.
REPO_CODE="$(curl -sS -o "$TMP_BODY" -w "%{http_code}" "${AUTH_HEADERS[@]}" "$REPO_API")"
if [ "$REPO_CODE" != "200" ]; then
  echo "BLAD: brak dostepu do repo (${OWNER}/${REPO}), HTTP $REPO_CODE"
  cat "$TMP_BODY"
  echo
  echo "Wskazowka: sprawdz TARGET_OWNER/TARGET_REPO oraz uprawnienia tokena."
  exit 1
fi

# 2) Lista workflow z docelowego repo.
WF_CODE="$(curl -sS -o "$TMP_WORKFLOWS" -w "%{http_code}" "${AUTH_HEADERS[@]}" "$WORKFLOWS_API")"
if [ "$WF_CODE" != "200" ]; then
  echo "BLAD: nie moge pobrac listy workflow, HTTP $WF_CODE"
  cat "$TMP_WORKFLOWS"
  echo
  echo "Wskazowka: token musi miec uprawnienia do GitHub Actions dla tego repo."
  exit 1
fi

WF_ROWS="$(
  tr -d '\n' < "$TMP_WORKFLOWS" \
  | sed 's/},{/}\n{/g' \
  | sed -nE 's/.*"id":[[:space:]]*([0-9]+).*"path":[[:space:]]*"([^"]+)".*/\1 \2/p'
)"

if [ -z "$WF_ROWS" ]; then
  echo "BLAD: repo nie zwrocilo workflow (pusta lista)."
  echo "Wskazowka: sprawdz czy workflow istnieje w .github/workflows/ na branchu '$REF'."
  exit 1
fi

TARGET_PATH=".github/workflows/${WORKFLOW_FILE}"
RESOLVED_WORKFLOW_ID="$WORKFLOW_ID"

if [ -z "$RESOLVED_WORKFLOW_ID" ]; then
  RESOLVED_WORKFLOW_ID="$(echo "$WF_ROWS" | awk -v target="$TARGET_PATH" '$2==target {print $1; exit}')"
fi

if [ -z "$RESOLVED_WORKFLOW_ID" ]; then
  echo "BLAD: nie znaleziono workflow pliku '$TARGET_PATH' w repo ${OWNER}/${REPO}."
  echo "Dostepne workflow (id path):"
  echo "$WF_ROWS" | sed 's/^/  - /'
  echo
  echo "Wskazowka: podaj poprawny TARGET_WORKFLOW_FILE albo TARGET_WORKFLOW_ID."
  exit 1
fi

# 3) Dispatch.
DISPATCH_API="${REPO_API}/actions/workflows/${RESOLVED_WORKFLOW_ID}/dispatches"
HTTP_CODE="$(curl -sS -o "$TMP_BODY" -w "%{http_code}" -X POST "${AUTH_HEADERS[@]}" "$DISPATCH_API" -d "{\"ref\":\"$REF\"}")"

if [ "$HTTP_CODE" = "204" ]; then
  echo "OK: workflow uruchomiony (id=${RESOLVED_WORKFLOW_ID}, ref=${REF})."
  exit 0
fi

echo "BLAD: GitHub API zwrocilo HTTP $HTTP_CODE przy dispatch."
cat "$TMP_BODY"
echo

if [ "$HTTP_CODE" = "404" ]; then
  echo "Wskazowka: workflow nie istnieje na branchu '$REF' albo token nie ma dostepu."
fi

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
  echo "Wskazowka: sprawdz token i uprawnienia do Actions (run workflow)."
fi

exit 1
