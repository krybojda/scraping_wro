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

# 4. Wyślij wyniki (mieszkania_vps.csv) do repozytorium
git add mieszkania_vps.csv >> scraper.log 2>&1
git commit -m "Auto-update VPS: $(date +'%Y-%m-%d')" >> scraper.log 2>&1
git push origin main >> scraper.log 2>&1

# Logowanie końca
echo "--- KONIEC: $(date) ---" >> scraper.log