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

# Sprawdzamy czy są w ogóle jakieś zmiany do wysłania
if git diff --staged --quiet; then
    echo "Brak zmian w bazie danych. Nie wysyłam." >> $LOGfile
else
    # 1. Zrób Commit lokalnie (Zapisz u siebie)
    git commit -m "RPi: Nowe dane szczegółowe [$(date +'%Y-%m-%d %H:%M')]" >> $LOGfile 2>&1
    
    # 2. POBIERZ ZMIANY Z VPS (To jest ten magiczny fix!)
    # --rebase sprawia, że Twoje zmiany zostaną nałożone "na wierzch" zmian z VPS
    echo "Pobieram ewentualne zmiany z VPS..." >> $LOGfile
    git pull --rebase origin main >> $LOGfile 2>&1
    
    # 3. Wyślij wszystko do chmury
    echo "Wysyłam do GitHub..." >> $LOGfile
    git push origin main >> $LOGfile 2>&1
fi

echo "=== KONIEC: $(date) ===" >> $LOGfile