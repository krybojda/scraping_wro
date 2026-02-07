import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os
from datetime import datetime

# --- KONFIGURACJA PRZEZ ZMIENNE ŚRODOWISKOWE ---

# Domyślna nazwa pliku, jeśli nie podasz innej
FILE_NAME = os.getenv("OUTPUT_FILE", "mieszkania_wroclaw.csv")

# Domyślny czas: 6 godzin (21600s), jeśli nie podasz innej wartości
# GitHub Actions nadpisze to na 3300s (55 min)
MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", 21600))

BASE_URL = "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/dolnoslaskie/wroclaw/wroclaw/wroclaw?limit=36&ownerTypeSingleSelect=ALL&by=DEFAULT&direction=DESC&viewType=listing"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'pl-PL'
}

START_TIME = time.time()

def get_listing_details(url):
    """Pobiera szczegóły pojedynczego ogłoszenia"""
    try:
        # Losowe opóźnienie 5-15 sek (bezpieczne dla obu trybów)
        time.sleep(random.uniform(5, 15))
        
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200: return None
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # --- EKSTRAKCJA (Uproszczona) ---
        title = soup.find('h1', {'data-cy': 'adPageAdTitle'})
        title = title.text.strip() if title else "Brak tytułu"

        price = soup.find('strong', {'data-cy': 'adPageHeaderPrice'})
        price = price.text.replace('zł', '').replace(' ', '').strip() if price else "0"

        # Szukanie metrażu w tekście (najbardziej uniwersalne)
        details_text = soup.text
        area = "0"
        if 'Powierzchnia' in details_text:
             # Bardzo prosta heurystyka, w produkcji warto użyć RegEx
             pass 

        return {
            'data_pobrania': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'tytul': title,
            'cena': price,
            'link': url
            # Tu dodaj resztę pól (pokoje, piętro itp.)
        }
    except:
        return None

def main():
    print(f"--- START SCRAPERA ---")
    print(f"Plik wyjściowy: {FILE_NAME}")
    print(f"Limit czasu: {MAX_EXECUTION_TIME / 60:.1f} minut")
    
    all_data = []
    page_number = 1
    
    while True:
        # SPRAWDZENIE CZASU
        elapsed = time.time() - START_TIME
        if elapsed > MAX_EXECUTION_TIME:
            print(f"!!! LIMIT CZASU ({MAX_EXECUTION_TIME}s) OSIĄGNIĘTY. ZAPISUJĘ. !!!")
            break

        print(f"\nSkanuję stronę listy nr {page_number}...")
        
        try:
            # Pobierz listę
            resp = requests.get(f"{BASE_URL}&page={page_number}", headers=HEADERS)
            if resp.status_code != 200: break
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            articles = soup.find_all('a', {'data-cy': 'listing-item-link'})
            
            if not articles:
                print("Koniec ogłoszeń.")
                break

            links = ["https://www.otodom.pl" + a['href'] for a in articles]
            
            # Pętla po ogłoszeniach
            for link in links:
                # Ponowne sprawdzenie czasu wewnątrz pętli
                if (time.time() - START_TIME) > MAX_EXECUTION_TIME:
                    break
                
                print(f" -> Pobieram ofertę: {link[-20:]}")
                details = get_listing_details(link)
                if details: all_data.append(details)

            page_number += 1
            time.sleep(random.uniform(2, 5)) # Krótka przerwa między stronami listy

        except Exception as e:
            print(f"Błąd: {e}")
            break

    # ZAPIS
    if all_data:
        df = pd.DataFrame(all_data)
        file_exists = os.path.isfile(FILE_NAME)
        df.to_csv(FILE_NAME, mode='a', header=not file_exists, index=False)
        print(f"Zapisano {len(all_data)} wierszy.")

if __name__ == "__main__":
    main()