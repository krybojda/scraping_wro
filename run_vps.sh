#!/bin/bash
set -euo pipefail

# 1. Przejdz do katalogu projektu (ZMIEN TE SCIEZKE NA SWOJA!)
cd /home/ubuntu/scraping_wro

# Plik logu (jak na RPi – jeden plik dzienny w katalogu logs/)
mkdir -p logs
LOGFILE="logs/log_$(date +%F).txt"

# Sprzatanie kontenera nawet gdy skrypt zakonczy sie bledem lub time-outem
cleanup() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
  if [ -n "${LOG_PID:-}" ] && ps -p "$LOG_PID" >/dev/null 2>&1; then
    kill "$LOG_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# Logowanie startu
echo "--- START: $(date) ---" >> "$LOGFILE"

# 2. Pobierz najnowsze zmiany z GitHub (zeby miec plik actions.csv)
# Uzywamy flagi --rebase, zeby uniknac problemow przy laczeniu historii
git pull --rebase origin main >> "$LOGFILE" 2>&1

# 3. Uruchom scrapera (Docker Compose)
# Uruchamiamy w tle, a logi streamujemy na biezaco do pliku
docker compose up -d --build >> "$LOGFILE" 2>&1

CID=$(docker compose ps -q scraper-vps)
if [ -z "$CID" ]; then
  echo "Nie znaleziono kontenera scraper-vps" | tee -a "$LOGFILE"
  exit 1
fi

# Stream logow do pliku, bez zatrzymywania kontenera
docker compose logs -f scraper-vps >> "$LOGFILE" 2>&1 &
LOG_PID=$!

# Czekaj az kontener skonczy prace
docker wait "$CID" >/dev/null 2>&1 || true

# 4. NAPRAWA UPRAWNIEN (Kluczowe dla Dockera!)
# Docker tworzy pliki jako root. Zmieniamy wlasciciela na obecnego uzytkownika (ubuntu)
sudo chown $USER:$USER *.csv 2>/dev/null

# 5. Wyslij wyniki (mieszkania_vps.csv) do repozytorium
# Przechodzimy do folderu (na wszelki wypadek)
cd "$(dirname "$0")"

# Dodajemy plik wygenerowany przez VPS
git add mieszkania_vps.csv

# Sprawdzamy czy sa zmiany
if git diff --staged --quiet; then
    echo "VPS: Brak nowych linkow. Nie wysylam." >> "$LOGFILE"
else
    # 1. Zapisz zmiany u siebie (lokalnie na VPS)
    git commit -m "VPS: Nowe linki [$(date +'%Y-%m-%d %H:%M')]" >> "$LOGFILE" 2>&1
    
    # 2. POBIERZ ZMIANY Z RPi / GITHUB ACTIONS (Kluczowy moment!)
    echo "VPS: Pobieram zmiany z serwera (Rebase)..." >> "$LOGFILE"
    git pull --rebase origin main >> "$LOGFILE" 2>&1
    
    # 3. Wyslij polaczone zmiany
    echo "VPS: Wysylam do GitHub..." >> "$LOGFILE"
    git push origin main >> "$LOGFILE" 2>&1
fi

# Logowanie zakonczenia
echo "=== KONIEC: $(date) ===" >> "$LOGFILE"
