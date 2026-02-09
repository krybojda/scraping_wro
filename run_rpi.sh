#!/bin/bash

# 1. Przejdź do folderu na pendrivie
cd /mnt/pendrive/Scraping_wro || exit

# 2. Logi zapisuj do tymczasowej pamięci RAM (/tmp), żeby nie zajechać karty SD/Pendrive'a ciągłym pisaniem
LOGfile="/tmp/scraper_rpi.log"

echo "=== START RPi: $(date) ===" >> $LOGfile

# 3. Pobierz nowe dane (lista linków)
git pull --rebase origin main >> $LOGfile 2>&1

# 4. Uruchom procesor (głębokie skrapowanie + discord)
# Używamy python3 zainstalowanego w systemie
python3 processor.py >> $LOGfile 2>&1

# 5. Wyślij bazę danych (Master File)
git add mieszkania_complete.csv >> $LOGfile 2>&1

if git diff --staged --quiet; then
    echo "Brak zmian w bazie danych." >> $LOGfile
else
    git commit -m "RPi: Nowe dane szczegółowe" >> $LOGfile 2>&1
    git push origin main >> $LOGfile 2>&1
fi

echo "=== KONIEC ===" >> $LOGfile