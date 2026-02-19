#!/bin/bash

# Zmień te dane na swoje:
TOKEN="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"
WŁAŚCICIEL="krybojda"
REPO="scraping_wro"
NAZWA_PLIKU_YML="combo-scraper.yml" # nazwa Twojego pliku workflow

curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/$WŁAŚCICIEL/$REPO/actions/workflows/$NAZWA_PLIKU_YML/dispatches \
  -d '{"ref":"main"}'

echo "Wysłano sygnał do GitHuba!"