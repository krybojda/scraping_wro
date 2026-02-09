#!/bin/bash

# 1. Przejdź do katalogu projektu (ZMIEN TĘ ŚCIEŻKĘ NA SWOJĄ!)
cd /home/ubuntu/Scraping_wro

# Logowanie startu
echo "--- START: $(date) ---" >> scraper.log

# 2. Pobierz najnowsze zmiany z GitHub (żeby mieć plik actions.csv)
# Używamy flagi --rebase, żeby uniknąć problemów przy łączeniu historii
git pull --rebase origin main >> scraper.log 2>&1

# 3. Uruchom scrapera (Docker Compose)
# To polecenie zablokuje skrypt na 6 godzin, dopóki kontener nie skończy pracy
# >> oznacza "dopisz na końcu pliku"
# 2>&1 oznacza "zapisz też błędy (stderr) w tym samym miejscu co zwykłe napisy"
docker compose up --build >> scraper_output.log 2>&1

# 4. NAPRAWA UPRAWNIEŃ (Kluczowe dla Dockera!)
# Docker tworzy pliki jako root. Zmieniamy właściciela na obecnego użytkownika (ubuntu)
sudo chown $USER:$USER *.csv 2>/dev/null

# 5. Wyślij wyniki (mieszkania_vps.csv) do repozytorium
# Przechodzimy do folderu (na wszelki wypadek)
cd "$(dirname "$0")"

# Dodajemy plik wygenerowany przez VPS
git add mieszkania_vps.csv

# Sprawdzamy czy są zmiany
if git diff --staged --quiet; then
    echo "VPS: Brak nowych linków. Nie wysyłam."
else
    # 1. Zapisz zmiany u siebie (lokalnie na VPS)
    git commit -m "VPS: Nowe linki [$(date +'%Y-%m-%d %H:%M')]" >> scraper.log 2>&1
    
    # 2. POBIERZ ZMIANY Z RPi / GITHUB ACTIONS (Kluczowy moment!)
    echo "VPS: Pobieram zmiany z serwera (Rebase)..."
    git pull --rebase origin main >> scraper.log 2>&1
    
    # 3. Wyślij połączone zmiany
    echo "VPS: Wysyłam do GitHub..."
    git push origin main >> scraper.log 2>&1
fi

# Logowanie zakończenia
echo "=== KONIEC: $(date) ===" >> scraper.log
fi
