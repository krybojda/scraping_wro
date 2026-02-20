#!/bin/bash
# shellcheck disable=SC2129

# --- KONFIGURACJA ---
CDir="$(cd "$(dirname "$0")" && pwd)"
LOGfile="$CDir/logs/log_$(date +'%Y-%m-%d').txt"

mkdir -p "$CDir/logs"
cd "$CDir" || { echo "❌ BŁĄD: Nie znaleziono katalogu $CDir" >> "/var/log/syslog"; exit 1; }

echo "=== START: $(date) ===" >> "$LOGfile"
rm -f .git/index.lock

# 1. IP
PUBLIC_IP="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || echo "BRAK_SIECI")"
echo "Public IP: $PUBLIC_IP" >> "$LOGfile"

# 2. AKTUALIZACJA KODU
if [ -z "${CI:-}" ]; then
    echo "📥 [GIT] Pobieranie zmian (RPi)..." >> "$LOGfile"
    git pull --rebase origin main >> "$LOGfile" 2>&1
else
    echo "🚀 [CI] Pomijam git pull (kod już jest aktualny)" >> "$LOGfile"
fi

# 3. URUCHOMIENIE BOTA
echo "🤖 [PYTHON] Start processora..." | tee -a "$LOGfile"
timeout 5h python3 -u processor.py 2>&1 | tee -a "$LOGfile" || true

echo "--- Python zakończył pracę. Rozpoczynam synchronizację... ---" >> "$LOGfile"

# =========================================================================
# 4. AKTUALIZACJA README I PRZYGOTOWANIE PLIKÓW (NOWA LOGIKA)
# =========================================================================

# Najpierw pobieramy najnowsze zmiany z chmury, żeby mieć świeże readme.md
if [ -z "${CI:-}" ]; then
    git pull --rebase origin main >> "$LOGfile" 2>&1
fi

# Jeśli Python wygenerował brudnopis ze statystykami, wklejamy go w odpowiednie miejsce
if [ -f "temp_processor.txt" ]; then
    echo "📝 Wklejam nowe statystyki do readme.md..." | tee -a "$LOGfile"
    python3 update_readme.py >> "$LOGfile" 2>&1
fi

# Dodajemy pliki
git add ./*.csv >> "$LOGfile" 2>&1
[ -f readme.md ] && git add readme.md >> "$LOGfile" 2>&1

# Sprawdzamy czy są zmiany
if git diff --quiet && git diff --staged --quiet; then
    echo "Brak zmian w danych. Nie wysyłam." | tee -a "$LOGfile"
    rm -f temp_processor.txt temp_scraper.txt 2>/dev/null # sprzątamy
    exit 0
fi

# =========================================================================
# 5. WYSYŁANIE (PUSH) Z PĘTLĄ RETRY
# =========================================================================
if [ -z "${CI:-}" ] || [ "${TRYB_MASTER:-}" = "true" ]; then

  echo "Wykryto zmiany i tryb zapisu. Commituję..." | tee -a "$LOGfile"
  git commit -m "Auto-zapis Node $(hostname): $(date +'%Y-%m-%d %H:%M')" >> "$LOGfile" 2>&1

  echo "🔄 [GIT] Rozpoczynam procedurę bezpiecznego zapisu (Pętla Retry)..." | tee -a "$LOGfile"

  MAX_RETRIES=5
  count=0
  success=false

  while [ $count -lt $MAX_RETRIES ]; do
      echo "   Próba synchronizacji $((count+1))/$MAX_RETRIES..." | tee -a "$LOGfile"

      # 1. Pobierz zmiany z serwera (Rebase)
      if git pull --rebase origin main >> "$LOGfile" 2>&1; then
          echo "   ✅ Rebase OK." | tee -a "$LOGfile"
      else
          echo "   ⚠️ Konflikt przy pobieraniu! Rozwiązuję inteligentnie..." | tee -a "$LOGfile"
          # PRZERWANY REBASE - Pora na "magię" naprawczą:
          git rebase --abort >> "$LOGfile" 2>&1
          git reset --soft HEAD~1 >> "$LOGfile" 2>&1         # Cofamy nasz commit
          git restore --staged readme.md >> "$LOGfile" 2>&1  # Odznaczamy readme
          git restore readme.md >> "$LOGfile" 2>&1           # Przywracamy czyste readme z serwera
          
          # Pobieramy czysty kod z serwera jeszcze raz
          git pull --rebase origin main >> "$LOGfile" 2>&1
          
          # Wklejamy nasze statystyki na najświeższy, pobrany plik
          if [ -f "temp_processor.txt" ]; then
              python3 zaktualizuj_readme.py >> "$LOGfile" 2>&1
              git add readme.md >> "$LOGfile" 2>&1
          fi
          
          # Robimy commit od nowa
          git commit -m "Auto-zapis Node $(hostname): $(date +'%Y-%m-%d %H:%M')" >> "$LOGfile" 2>&1
          
          count=$((count+1))
          sleep 5
          continue
      fi

      # 2. Spróbuj wysłać
      if git push origin main >> "$LOGfile" 2>&1; then
          echo "🚀 SUKCES! Dane wysłane bezpiecznie." | tee -a "$LOGfile"
          rm -f temp_processor.txt # Sprzątamy po udanym wysłaniu
          success=true
          break
      else
          echo "   ⛔ Push odrzucony (ktoś nas ubiegł?). Czekam i ponawiam..." | tee -a "$LOGfile"
          count=$((count+1))
          sleep $((RANDOM % 10 + 5)) # Czekaj losowo 5-15 sekund
      fi
  done

  if [ "$success" = false ]; then
      echo "❌ KRYTYCZNY BŁĄD GITA: Nie udało się wysłać zmian po $MAX_RETRIES próbach." | tee -a "$LOGfile"
      exit 1
  fi

else
    echo "⚠️ Tryb testowy (CI bez uprawnień). Zmiany nie zostały wysłane." | tee -a "$LOGfile"
fi

echo "=== KONIEC: $(date) ===" >> "$LOGfile"
echo "" >> "$LOGfile"
