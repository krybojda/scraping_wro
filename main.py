import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os
import re
import csv
from datetime import datetime
from fake_useragent import UserAgent  # NOWOŚĆ

# --- KONFIGURACJA ---
FILE_NAME = os.getenv("OUTPUT_FILE", "mieszkania_wroclaw.csv")
MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", 21600))

BASE_URL = "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/dolnoslaskie/wroclaw/wroclaw/wroclaw?limit=36&ownerTypeSingleSelect=ALL&by=DEFAULT&direction=DESC&viewType=listing"

# Inicjalizacja generatora User-Agent
ua = UserAgent()
START_TIME = time.time()

def make_request(url):
    """Pobieranie z rotacją User-Agent"""
    try:
        # Losujemy przeglądarkę za każdym razem
        headers = {
            'User-Agent': ua.random,
            'Accept-Language': 'pl-PL'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code in [403, 429]:
            print(f"!!! BAN IP ({response.status_code}) !!!")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        if soup.title and "captcha" in soup.title.text.lower():
            print("!!! SOFT BAN (Captcha) !!!")
            return None

        return soup
    except Exception as e:
        print(f"Błąd sieci: {e}")
        return None

def get_listing_basic(url):
    """Szybkie pobieranie podstawowych danych (HTML)"""
    try:
        time.sleep(random.uniform(15, 60))  # Dłuższe przerwy między ogłoszeniami
        soup = make_request(url)
        if not soup: return None
        
        title = soup.find('h1', {'data-cy': 'adPageAdTitle'})
        title = title.text.strip() if title else "Brak tytułu"

        price = soup.find('strong', {'data-cy': 'adPageHeaderPrice'})
        price = price.text.replace('zł', '').replace(' ', '').strip() if price else "0"

        area = "0"
        found = re.search(r'(\d+[.,]?\d*)\s*m²', soup.text)
        if found:
            area = found.group(1).replace(',', '.').strip()

        return {
            'data_pobrania': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'tytul': title,
            'cena': price,
            'metraz': area,
            'link': url
        }
    except:
        return None

def main():
    print(f"--- START ZWIADOWCY --- Plik: {FILE_NAME}")
    page = 1
    
    while True:
        if (time.time() - START_TIME) > MAX_EXECUTION_TIME:
            print("Koniec czasu.")
            break

        print(f"Skanuję stronę {page}...")
        soup = make_request(f"{BASE_URL}&page={page}")
        if not soup: break

        articles = soup.find_all('a', {'data-cy': 'listing-item-link'})
        if not articles: break

        links = ["https://www.otodom.pl" + a['href'] for a in articles]
        
        page_data = []
        for link in links:
            if (time.time() - START_TIME) > MAX_EXECUTION_TIME: break
            
            print(f" -> {link[-20:]}")
            details = get_listing_basic(link)
            if details: page_data.append(details)

        if page_data:
            df = pd.DataFrame(page_data)
            exists = os.path.isfile(FILE_NAME)
            df.to_csv(
                FILE_NAME,
                mode='a',
                header=not exists,
                index=False,
                quoting=csv.QUOTE_MINIMAL,
                escapechar='\\'
            )
            print(f"Zapisano {len(page_data)} rekordów.")
        
        page += 1
        time.sleep(random.uniform(15, 60))  # Dłuższe przerwy między stronami

if __name__ == "__main__":
    main()
