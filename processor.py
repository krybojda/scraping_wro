import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import os
import json
from datetime import datetime
from fake_useragent import UserAgent

# --- KONFIGURACJA ---
FILE_GH = "mieszkania_gh.csv"
FILE_VPS = "mieszkania_vps.csv"
MASTER_FILE = "mieszkania_complete.csv"

# !!! TUTAJ WKLEJ SWÓJ LINK Z DISCORDA !!!
DISCORD_URL = "https://discord.com/api/webhooks/1470223047867764800/m08l3piGAiD5sSXnl2bTgJX1LRzopi9WBjSkqUp5s9eXRuXR6o4exmVLChVdWRIIk_R2"

ua = UserAgent()

def send_discord_alert(offer):
    """Wysyła ładne powiadomienie na Discord"""
    if "TWOJ_ID" in DISCORD_URL: return 

    embed = {
        "title": f"🏠 {offer.get('tytul', 'Nowa oferta')}",
        "url": offer['link'],
        "color": 5814783, 
        "fields": [
            {"name": "Cena", "value": f"{offer.get('cena', '?')} zł", "inline": True},
            {"name": "Czynsz", "value": f"{offer.get('czynsz', '?')}", "inline": True},
            {"name": "Metraż", "value": f"{offer.get('powierzchnia', '?')} m²", "inline": True},
            {"name": "Pokoje", "value": f"{offer.get('pokoje', '?')}", "inline": True},
            {"name": "Piętro", "value": f"{offer.get('pietro', '?')}", "inline": True},
            {"name": "Lokalizacja", "value": f"{offer.get('lokalizacja', '?')}", "inline": False}
        ],
        "footer": {"text": "Bot Nieruchomości RPi"}
    }
    
    payload = {"embeds": [embed]}
    try:
        requests.post(DISCORD_URL, json=payload)
    except Exception as e:
        print(f"Błąd Discorda: {e}")

def get_full_details_json(url):
    """Pobiera głębokie dane (JSON) z rotacją UA i DŁUGIM czasem oczekiwania"""
    try:
        # --- ZMIANA NA ULTRA-BEZPIECZNE CZASY ---
        # Losuje przerwę między 45 a 90 sekund. 
        # Średnio minuta na ogłoszenie. Wygląda jak czytanie ze zrozumieniem.
        sleep_time = random.uniform(45, 90)
        print(f"   (Czekam {sleep_time:.1f}s dla niepoznaki...)") 
        time.sleep(sleep_time)
        # ----------------------------------------
        
        headers = {'User-Agent': ua.random, 'Accept-Language': 'pl-PL'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code != 200: return None
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        data_script = soup.find('script', id='__NEXT_DATA__')
        
        if not data_script: return None
        
        json_data = json.loads(data_script.string)
        ad_data = json_data['props']['pageProps']['ad']
        target = ad_data['target']

        def get_char(key):
            for char in target.get('Characteristics', []):
                if char.get('key') == key:
                    return char.get('localizedValue')
            return ""

        # Budowanie lokalizacji
        loc_list = ad_data.get('location', {}).get('geoLocation', {}).get('breadcrumbs', [])
        lokalizacja = ", ".join([l.get('fullName') for l in loc_list])

        return {
            'czynsz': get_char('rent'),
            'pietro': get_char('floor_no'),
            'rok_budowy': get_char('build_year'),
            'ogrzewanie': get_char('heating'),
            'kaucja': get_char('security_security'),
            'pokoje': target.get('Rooms_num', ''),
            'stan': get_char('construction_status'),
            'lokalizacja': lokalizacja,
            'powierzchnia': target.get('Area', ''), 
            'data_aktualizacji': datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"Błąd przy {url}: {e}")
        return None

def main():
    print("--- START RPi PROCESSOR (Tryb Ultra-Safe) ---")

    # 1. Łączenie danych z VPS i GH
    dfs = []
    # Wczytywanie z obsługą błędów pustych plików
    if os.path.exists(FILE_GH): 
        try: dfs.append(pd.read_csv(FILE_GH))
        except: pass
    if os.path.exists(FILE_VPS): 
        try: dfs.append(pd.read_csv(FILE_VPS))
        except: pass
        
    if not dfs:
        print("Brak danych wejściowych.")
        return

    df_raw = pd.concat(dfs, ignore_index=True)
    df_unique = df_raw.drop_duplicates(subset='link', keep='last')

    # 2. Co już mamy?
    processed_links = []
    if os.path.exists(MASTER_FILE):
        try:
            df_master = pd.read_csv(MASTER_FILE)
            if 'link' in df_master.columns:
                processed_links = df_master['link'].tolist()
        except: pass

    # 3. Co trzeba pobrać?
    links_to_do = df_unique[~df_unique['link'].isin(processed_links)].to_dict('records')
    total = len(links_to_do)
    print(f"Znaleziono {total} nowych ogłoszeń do przetworzenia.")

    new_records = []
    for i, row in enumerate(links_to_do):
        print(f"[{i+1}/{total}] Przetwarzam: {row['link'][-20:]}")
        
        details = get_full_details_json(row['link'])
        
        if details:
            full_record = {**row, **details}
            new_records.append(full_record)
            
            # Warunek Discorda (np. cena > 0 żeby odsiać błędy)
            try:
                cena_clean = float(str(row.get('cena', '0')).replace(' ', '').replace(',', '.'))
                if cena_clean > 0: 
                    send_discord_alert(full_record)
            except: pass
        
        # Zapis co 1 rekord - przy tak wolnym tempie (co minutę)
        # lepiej zapisywać od razu, żeby nic nie stracić.
        df_new = pd.DataFrame(new_records)
        exists = os.path.exists(MASTER_FILE)
        df_new.to_csv(MASTER_FILE, mode='a', header=not exists, index=False)
        new_records = [] # Czyścimy bufor po zapisie

if __name__ == "__main__":
    main()