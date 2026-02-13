#!/bin/bash
set -euo pipefail

# Sciezka do repo na RPi
CDir="/mnt/pendrive/scraping_wro"
LOGfile="$CDir/logs/log_$(date +'%Y-%m-%d').txt"

# Upewnij sie, ze katalog na logi istnieje zanim cokolwiek przekierujemy
mkdir -p "$CDir/logs"
cd "$CDir"

echo "=== START: $(date) ===" >> "$LOGfile"

# IP diagnostycznie na starcie (publiczne)
PUBLIC_IP="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)"

if [ -n "$PUBLIC_IP" ]; then
  echo "Public IP: $PUBLIC_IP" | tee -a "$LOGfile"
else
  echo "Public IP: (nie udalo sie pobrac)" | tee -a "$LOGfile"
fi

# 1. Pobierz najnowsze zmiany z chmury (rebase minimalizuje konflikty)
git pull --rebase origin main >> "$LOGfile" 2>&1

# 2. Uruchom procesor (timeout 6h; || true pozwala dokonczyc skrypt mimo bledu/kill)
timeout 6h python3 -u processor.py >> "$LOGfile" 2>&1 || true

echo "--- Python zakonczyl prace. Rozpoczynam wysylanie... ---" >> "$LOGfile"

# 3. Dodaj i zatwierdz zmiany (tylko plik wyjściowy z RPi)
git add mieszkania_complete.csv >> "$LOGfile" 2>&1 || true

if git diff --cached --quiet; then
  echo "Brak nowych zmian do commitowania." >> "$LOGfile"
else
  git commit -m "RPI Auto-zapis: $(date +'%Y-%m-%d %H:%M')" >> "$LOGfile" 2>&1
fi

# 4. Pobierz ewentualne zmiany z GitHuba i nałóż swoje
git pull --rebase origin main >> "$LOGfile" 2>&1

# 5. Wyślij do chmury
git push >> "$LOGfile" 2>&1

echo "=== KONIEC: $(date) ===" >> "$LOGfile"
