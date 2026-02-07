import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os
import re  # Dodano do szukania liczb w tekście
from datetime import datetime

# --- KONFIGURACJA ---
FILE_NAME = os.getenv("OUTPUT_FILE", "mieszkania_wroclaw.csv")
MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", 21600))

BASE_URL = "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/dolnoslaskie/wroclaw/wroclaw/wroclaw?limit=36&ownerTypeSingleSelect=ALL&by=DEFAULT&direction=DESC&viewType=listing"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'pl-PL'
}

START_TIME = time.time()

def make_request(url):
    """Bezpieczne pobieranie z wykrywaniem bana"""
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code in [403, 429]:
            print(f"!!! BAN IP ({response.status_code}) - URL: {url}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Proste wykrywanie Captcha
        if soup.title and "captcha" in soup.title.text.lower():
            print("!!! SOFT BAN (Captcha) wykryty!")
            return None

        return soup
    except Exception as e:
        print(f"Błąd sieci: {e}")
        return None

def get_listing_details(url):
    """Pobiera szczegóły pojedynczego ogłoszenia"""
    try:
        # Losowe opóźnienie
        time.sleep(random.uniform(5, 15))
        
        soup = make_request(url)
        if not soup: return None
        
        # --- EKSTRAKCJA ---
        title = soup.find('h1', {'data-cy': 'adPageAdTitle'})
        title = title.text.strip() if title else "Brak tytułu"

        price = soup.find('strong', {'data-cy': 'adPageHeaderPrice'})
        price = price.text.replace('zł', '').replace(' ', '').strip() if price else "0"

        # Szukanie metrażu w tekście całej strony (metoda uniwersalna)
        details_text = soup.text
        area = "0"
        
        # Szukamy wzorca: liczba + m² (np. "45,5 m²")
        found = re.search(r'(\d+[.,]?\d*)\s*m²', details_text)
        if found:
            area = found.group(1).replace(',', '.').strip()

        return {
            'data_pobrania': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'tytul': title,
            'cena': price,
            'metraz': area,  # Dodano metraż
            'link': url
        }
    except Exception as e:
        print(f"Błąd parsowania: {e}")
        return None

def main():
    print(f"--- START SCRAPERA ---")
    print(f"Plik wyjściowy: {FILE_NAME}")
    print(f"Limit czasu: {MAX_EXECUTION_TIME / 60:.1f} minut")
    
    page_number = 1
    
    while True:
        # SPRAWDZENIE CZASU
        if (time.time() - START_TIME) > MAX_EXECUTION_TIME:
            print(f"!!! LIMIT CZASU OSIĄGNIĘTY. KOŃCZĘ. !!!")
            break

        print(f"\nSkanuję stronę listy nr {page_number}...")
        
        try:
            # Tu używamy lokalnej listy dla danej strony, żeby od razu zapisywać
            page_data = [] 
            
            # Pobierz listę
            soup = make_request(f"{BASE_URL}&page={page_number}")
            if not soup: 
                print("Błąd pobierania listy lub ban.")
                break

            articles = soup.find_all('a', {'data-cy': 'listing-item-link'})
            
            if not articles:
                print("Koniec ogłoszeń (brak wyników).")
                break

            links = ["https://www.otodom.pl" + a['href'] for a in articles]
            
            # Pętla po ogłoszeniach
            for link in links:
                if (time.time() - START_TIME) > MAX_EXECUTION_TIME:
                    break
                
                print(f" -> Pobieram ofertę: {link[-20:]}")
                details = get_listing_details(link)
                if details: 
                    page_data.append(details)

            # --- KLUCZOWA ZMIANA: ZAPISUJEMY PO KAŻDEJ STRONIE ---
            if page_data:
                df = pd.DataFrame(page_data)
                # Sprawdzamy czy plik istnieje, żeby wiedzieć czy dodać nagłówki
                file_exists = os.path.isfile(FILE_NAME)
                df.to_csv(FILE_NAME, mode='a', header=not file_exists, index=False)
                print(f"Zapisano {len(page_data)} wierszy z tej strony.")
            # -----------------------------------------------------

            page_number += 1
            time.sleep(random.uniform(2, 5))

        except Exception as e:
            print(f"Krytyczny błąd w pętli: {e}")
            break

if __name__ == "__main__":
    main()