#!/bin/bash
# shellcheck disable=SC2129
set -euo pipefail

if [ -n "${CI:-}" ]; then
  echo "run_vps.sh: tryb CI – pomijam pełne wykonanie."
  exit 0
fi

cd "$(dirname "$0")"

mkdir -p logs
LOGFILE="logs/log_$(date +%F).txt"

cleanup() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "--- START: $(date) ---" | tee -a "$LOGFILE"

# 2. Pobierz najnowsze zmiany z GitHub
if [ -z "${CI:-}" ]; then
  echo "📥 [GIT] Pobieram nowości z serwera..." | tee -a "$LOGFILE"
  git pull --rebase origin main 2>&1 | tee -a "$LOGFILE"
else
  echo "🚀 Tryb testowy (CI): Pomijam git pull" | tee -a "$LOGFILE"
fi

# 3. Uruchom scrapera (Docker Compose) - WIDOCZNY NA EKRANIE
echo "🐳 [DOCKER] Startuję Zwiadowcę..." | tee -a "$LOGFILE"

# Zamiast wysyłać w tło, odpalamy normalnie i łapiemy logi przez tee
docker compose up --build 2>&1 | tee -a "$LOGFILE"

# =========================================================================
# 4. NAPRAWA UPRAWNIEŃ I AKTUALIZACJA README
# =========================================================================

echo "🔧 Naprawiam uprawnienia plików po Dockerze..." | tee -a "$LOGFILE"
sudo chown "$USER":"$USER" ./*.csv readme.md temp_scraper.txt 2>/dev/null || true

if [ -z "${CI:-}" ]; then
    echo "📥 [GIT] Pobieram świeże readme.md..." | tee -a "$LOGFILE"
    git pull --rebase origin main 2>&1 | tee -a "$LOGFILE"
fi

if [ -f "temp_scraper.txt" ]; then
    echo "📝 Wklejam nowe statystyki Scrapera do readme.md..." | tee -a "$LOGFILE"
    python3 update_readme.py 2>&1 | tee -a "$LOGFILE"
fi

git add ./*.csv 2>&1 | tee -a "$LOGFILE"
[ -f readme.md ] && git add readme.md 2>&1 | tee -a "$LOGFILE"

if git diff --quiet && git diff --staged --quiet; then
    echo "🛑 VPS: Brak nowych linków. Nie wysyłam." | tee -a "$LOGFILE"
    rm -f temp_scraper.txt 2>/dev/null
    exit 0
fi

# =========================================================================
# 5. WYSYŁANIE (PUSH) Z PĘTLĄ RETRY
# =========================================================================

if [ -z "${CI:-}" ]; then
  echo "💾 VPS: Wykryto zmiany. Commituję..." | tee -a "$LOGFILE"
  git commit -m "VPS: Nowe linki [$(date +'%Y-%m-%d %H:%M')]" 2>&1 | tee -a "$LOGFILE"

  echo "🔄 [GIT] Rozpoczynam procedurę bezpiecznego zapisu (Pętla Retry)..." | tee -a "$LOGFILE"

  MAX_RETRIES=5
  count=0
  success=false

  while [ $count -lt $MAX_RETRIES ]; do
      echo "   Próba synchronizacji $((count+1))/$MAX_RETRIES..." | tee -a "$LOGFILE"

      if git pull --rebase origin main 2>&1 | tee -a "$LOGFILE"; then
          echo "   ✅ Rebase OK." | tee -a "$LOGFILE"
      else
          echo "   ⚠️ Konflikt przy pobieraniu! Rozwiązuję inteligentnie..." | tee -a "$LOGFILE"
          
          git rebase --abort 2>&1 | tee -a "$LOGFILE" || true
          git reset --soft HEAD~1 2>&1 | tee -a "$LOGFILE" || true
          git restore --staged readme.md 2>&1 | tee -a "$LOGFILE" || true
          git restore readme.md 2>&1 | tee -a "$LOGFILE" || true
          
          git pull --rebase origin main 2>&1 | tee -a "$LOGFILE"
          
          if [ -f "temp_scraper.txt" ]; then
              python3 zaktualizuj_readme.py 2>&1 | tee -a "$LOGFILE"
              git add readme.md 2>&1 | tee -a "$LOGFILE"
          fi
          
          git commit -m "VPS: Nowe linki [$(date +'%Y-%m-%d %H:%M')]" 2>&1 | tee -a "$LOGFILE"
          
          count=$((count+1))
          sleep 5
          continue
      fi

      if git push origin main 2>&1 | tee -a "$LOGFILE"; then
          echo "🚀 SUKCES! Dane wysłane bezpiecznie." | tee -a "$LOGFILE"
          rm -f temp_scraper.txt 2>/dev/null
          success=true
          break
      else
          echo "   ⛔ Push odrzucony (ktoś nas ubiegł?). Czekam i ponawiam..." | tee -a "$LOGFILE"
          count=$((count+1))
          sleep $((RANDOM % 10 + 5))
      fi
  done

  if [ "$success" = false ]; then
      echo "❌ KRYTYCZNY BŁĄD GITA: Nie udało się wysłać zmian po $MAX_RETRIES próbach." | tee -a "$LOGFILE"
      exit 1
  fi

else
  echo "⚠️ Tryb testowy (CI): Pomijam git push" | tee -a "$LOGFILE"
fi

echo "=== KONIEC: $(date) ===" | tee -a "$LOGFILE"
