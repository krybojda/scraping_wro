#!/bin/bash

# Ustawienia
CDir="/mnt/pendrive/Scraping_wro"
LOGfile="$CDir/logs/log_$(date +'%Y-%m-%d').txt"

cd "$CDir"

echo "=== START: $(date) ===" >> "$LOGfile"

# 1. Pobierz najnowsze zmiany z chmury (żeby uniknąć konfliktów na starcie)
git pull --rebase origin main >> "$LOGfile" 2>&1

# 2. Uruchom Pythona ( || true sprawia, że skrypt nie umiera po pkill/błędzie)
#    Timeout ustawiony na 2h dla bezpieczeństwa
timeout 6h python3 -u processor.py >> "$LOGfile" 2>&1 || true

echo "--- Python zakończył pracę. Rozpoczynam wysyłanie... ---" >> "$LOGfile"

# 3. Dodaj i zatwierdź zmiany
git add . >> "$LOGfile" 2>&1
git commit -m "Auto-zapis: $(date +'%Y-%m-%d %H:%M')" >> "$LOGfile" 2>&1 || echo "Brak nowych zmian do commitowania." >> "$LOGfile"

# 4. KLUCZOWE: Pobierz ewentualne zmiany z GitHuba i nałóż swoje
git pull --rebase origin main >> "$LOGfile" 2>&1

# 5. Wyślij do chmury
git push >> "$LOGfile" 2>&1

echo "=== KONIEC: $(date) ===" >> "$LOGfile"