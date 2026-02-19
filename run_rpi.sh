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
# ZMIANA: Robimy git pull TYLKO jeśli NIE jesteśmy w GitHub Actions (CI)
# W Actions kod jest już pobrany przez 'actions/checkout'
if [ -z "${CI:-}" ]; then
    echo "📥 [GIT] Pobieranie zmian (RPi)..." >> "$LOGfile"
    git pull --rebase origin main >> "$LOGfile" 2>&1
else
    echo "🚀 [CI] Pomijam git pull (kod już jest aktualny)" >> "$LOGfile"
fi

# 3. URUCHOMIENIE BOTA
# ZMIANA: Używamy '| tee -a', żeby widzieć logi w Actions NA ŻYWO!
echo "🤖 [PYTHON] Start processora..." | tee -a "$LOGfile"
# 2>&1 przekierowuje błędy do standardowego wyjścia, a tee rzuca to na ekran i do pliku
timeout 5h python3 -u processor.py 2>&1 | tee -a "$LOGfile" || true

echo "--- Python zakończył pracę. Rozpoczynam synchronizację... ---" >> "$LOGfile"

# 4. PRZYGOTOWANIE PLIKÓW
git add ./*.csv >> "$LOGfile" 2>&1

# Sprawdzamy czy są zmiany
if git diff --quiet && git diff --staged --quiet; then
    echo "Brak zmian w danych. Nie wysyłam." | tee -a "$LOGfile"
    exit 0
fi

# 5. WYSYŁANIE (PUSH)
# Działa na RPi (brak CI) LUB na Actions w trybie MASTER
if [ -z "${CI:-}" ] || [ "${TRYB_MASTER:-}" = "true" ]; then

  echo "Wykryto zmiany i tryb zapisu. Commituję..." | tee -a "$LOGfile"

  git commit -m "Auto-zapis Node $(hostname): $(date +'%Y-%m-%d %H:%M')" >> "$LOGfile" 2>&1
  
  echo "🔄 [GIT] Pobieranie i łączenie zmian (Rebase)..." >> "$LOGfile"
  # Tutaj pull jest konieczny, bo w międzyczasie inny bot mógł coś wrzucić
  git pull --rebase origin main >> "$LOGfile" 2>&1
  
  echo "📤 [GIT] Wysyłanie do chmury..." | tee -a "$LOGfile"
  git push origin main >> "$LOGfile" 2>&1

  echo "✅ Sukces! Dane wysłane na GitHub." | tee -a "$LOGfile"

else
    echo "⚠️ Tryb testowy (CI bez uprawnień). Zmiany nie zostały wysłane." | tee -a "$LOGfile"
fi

echo "=== KONIEC: $(date) ===" >> "$LOGfile"
echo "" >> "$LOGfile"