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

def send_discord_alert(offer, type="Nowa oferta"):
    """Wysyła ładne powiadomienie na Discord"""
    if "TWOJ_ID" in DISCORD_URL: return 

    color = 5814783 if type == "Nowa oferta" else 16776960 # Zielony dla nowych, Żółty dla zmian

    embed = {
        "title": f"🏠 {type}: {offer.get('tytul', 'Ogłoszenie')}",
        "url": offer['link'],
        "color": color, 
        "fields": [
            {"name": "Cena", "value": f"{offer.get('cena', '?')} zł", "inline": True},
            {"name": "Czynsz", "value": f"{offer.get('czynsz', '?')}", "inline": True},
            {"name": "Metraż", "value": f"{offer.get('powierzchnia', '?')} m²", "inline": True},
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
        sleep_time = random.uniform(45, 90)
        print(f"   (Czekam {sleep_time:.1f}s...)") 
        time.sleep(sleep_time)
        
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
    print("--- START RPi PROCESSOR (Tryb: Inteligentna Aktualizacja) ---")

    # 1. Łączenie danych z VPS i GH (z naprawą błędów CSV)
    dfs = []
    if os.path.exists(FILE_GH): 
        try: dfs.append(pd.read_csv(FILE_GH, on_bad_lines='skip'))
        except: pass
    if os.path.exists(FILE_VPS): 
        try: dfs.append(pd.read_csv(FILE_VPS, on_bad_lines='skip'))
        except: pass
        
    if not dfs:
        print("Brak danych wejściowych.")
        return

    df_raw = pd.concat(dfs, ignore_index=True)
    # Usuwamy duplikaty wewnątrz plików wejściowych
    df_unique = df_raw.drop_duplicates(subset='link', keep='last')

    # 2. Wczytanie starej bazy do słownika {link: cena}
    processed_prices = {}
    if os.path.exists(MASTER_FILE):
        try:
            df_master = pd.read_csv(MASTER_FILE)
            if 'link' in df_master.columns and 'cena' in df_master.columns:
                # Tworzymy słownik {link: "1234 zł"}
                processed_prices = pd.Series(df_master.cena.values, index=df_master.link).to_dict()
        except: pass

    # 3. Wybór ogłoszeń do przetworzenia
    links_to_do = []
    
    for record in df_unique.to_dict('records'):
        link = record['link']
        new_price = str(record.get('cena', '')).strip()
        
        # Jeśli linku nie ma w bazie -> NOWE
        if link not in processed_prices:
            record['typ_akcji'] = "NOWE"
            links_to_do.append(record)
        
        # Jeśli link jest, ale cena inna -> AKTUALIZACJA
        else:
            old_price = str(processed_prices[link]).strip()
            # Proste porównanie napisów (np. "2500 zł" vs "2500")
            # Czyścimy spacje i "zł" dla pewności
            np_clean = new_price.replace(' ', '').replace('zł', '')
            op_clean = old_price.replace(' ', '').replace('zł', '')
            
            if np_clean != op_clean and np_clean and op_clean:
                record['typ_akcji'] = "ZMIANA CENY"
                print(f"(!) Zmiana ceny dla {link[-15:]}: {old_price} -> {new_price}")
                links_to_do.append(record)

    total = len(links_to_do)
    print(f"Znaleziono {total} ogłoszeń (Nowe + Zmiany cen). Pominięto {len(df_unique) - total} bez zmian.")

    # 4. Przetwarzanie
    new_records = []
    for i, row in enumerate(links_to_do):
        print(f"[{i+1}/{total}] [{row['typ_akcji']}] {row['link'][-20:]}")
        
        details = get_full_details_json(row['link'])
        
        if details:
            full_record = {**row, **details}
            new_records.append(full_record)
            
            # Discord - wyślij powiadomienie
            try:
                msg_type = "Nowa oferta" if row['typ_akcji'] == "NOWE" else "📉 Zmiana ceny"
                send_discord_alert(full_record, type=msg_type)
            except: pass
        
        # Zapisz od razu do CSV
        df_new = pd.DataFrame(new_records)
        exists = os.path.exists(MASTER_FILE)
        df_new.to_csv(MASTER_FILE, mode='a', header=not exists, index=False)
        new_records = [] 

if __name__ == "__main__":
    main()