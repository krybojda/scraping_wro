#!/bin/bash

# 1. Przejdź do folderu na pendrivie
cd /mnt/pendrive/Scraping_wro || exit

# Nazwa pliku zawiera datę, np. log_2023-10-27.txt
LOGfile="logs/log_$(date +%F).txt"
mkdir -p logs  # upewnij się, że folder istnieje

# --- BEZPIECZNY START (Zapisz zamiast kasować) ---

# 1. Najpierw dodaj wszystko, co RPi zdążyło "wymęczyć" przed awarią
if [ -f mieszkania_complete.csv ]; then
    git add mieszkania_complete.csv
else
    echo "Brak mieszkania_complete.csv - pomijam git add (przed pull)" >> $LOGfile
fi

# 2. Spróbuj zrobić commit (zabezpiecz dane w lokalnej historii)
# Jeśli nie ma zmian, komenda po "||" sprawi, że skrypt pójdzie dalej bez błędu
git commit -m "AUTO-SAVE: Odzyskanie danych po przerwaniu skryptu" || echo "Brak niezapisanych zmian - czysto." >> $LOGfile 2>&1

# 3. Teraz, gdy zmiany są bezpieczne w "sejfie" (commicie), możesz bezpiecznie pobrać nowości
# Używamy --rebase, żeby Twoje odzyskane dane zostały "na wierzchu"
echo "Pobieram nowości z VPS..." >> $LOGfile
git pull --rebase origin main >> $LOGfile 2>&1

# -------------------------------------------------

# 4. Uruchom procesor (głębokie skrapowanie + discord)
# Używamy python3 zainstalowanego w systemie
python3 -u processor.py >> $LOGfile 2>&1

# 5. Wyślij bazę danych (Master File)
if [ -f mieszkania_complete.csv ]; then
    git add mieszkania_complete.csv >> $LOGfile 2>&1
else
    echo "Brak mieszkania_complete.csv - pomijam git add (po procesie)" >> $LOGfile
fi

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
