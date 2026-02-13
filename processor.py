import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import os
import json
import csv
import re
from datetime import datetime
from fake_useragent import UserAgent

# --- KONFIGURACJA ---
FILE_GH = "mieszkania_gh.csv"
FILE_VPS = "mieszkania_vps.csv"
MASTER_FILE = "mieszkania_complete.csv"

# Konfiguracja maszyn
NODE_ID = 0
TOTAL_NODES = 1

DISCORD_URL = "https://discord.com/api/webhooks/1470223047867764800/m08l3piGAiD5sSXnl2bTgJX1LRzopi9WBjSkqUp5s9eXRuXR6o4exmVLChVdWRIIk_R2"

ua = UserAgent()

FINAL_COLUMNS = [
    'data_pobrania', 'tytul', 'cena', 'link', 'aneks', 
    'czynsz', 'pietro', 'pokoje', 'lokalizacja', 
    'rok_budowy', 'ogrzewanie', 'kaucja', 'stan', 
    'powierzchnia', 'data_aktualizacji'
]

# --- FUNKCJE POMOCNICZE ---
def normalize_link(link: str) -> str:
    if not isinstance(link, str): return ""
    cleaned = link.strip()
    cleaned = cleaned.replace("://www.otodom.pl/hpr", "://www.otodom.pl")
    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0]
    return cleaned.rstrip("/")

def offer_id_from_link(link: str) -> str:
    m = re.search(r"(ID[0-9A-Za-z]+)", link or "", re.IGNORECASE)
    return m.group(1).upper() if m else ""

def dedupe_key_from_link(link: str) -> str:
    norm = normalize_link(link)
    oid = offer_id_from_link(norm)
    return oid or norm

def clean_duplicates_in_master():
    """
    Usuwa TYLKO zduplikowane wiersze (linki).
    NIE ZMIENIA WARTOŚCI W KOMÓRKACH (szanuje historię np. '—').
    """
    if not os.path.exists(MASTER_FILE): return
    try:
        # Wczytujemy wszystko jako tekst (dtype=str), żeby pandas nie zamieniał '—' na NaN
        df = pd.read_csv(MASTER_FILE, dtype=str)
        
        if 'link' not in df.columns: return
        
        initial_len = len(df)
        df['dedupe_key'] = df['link'].apply(dedupe_key_from_link)
        
        # Usuwamy duplikaty (zostawiamy ostatni napotkany)
        df = df.drop_duplicates(subset=['dedupe_key'], keep='last')
        
        # Usuwamy kolumnę pomocniczą
        df = df.drop(columns=['dedupe_key'])
        
        final_len = len(df)
        if initial_len != final_len:
            print(f"🧹 AUTOCZYSZCZENIE: Usunięto {initial_len - final_len} duplikatów.")
            # Zapisujemy bez zmian w treści
            df.to_csv(MASTER_FILE, index=False)
    except Exception as e:
        print(f"Błąd autoczyszczenia: {e}")

def send_discord_alert(offer, type="Nowa oferta"):
    if "TWOJ_ID" in DISCORD_URL: return False
    
    if type == "Nowa oferta": color = 5814783
    elif "BAN" in type or "CAPTCHA" in type: color = 15548997
    else: color = 16776960

    embed = {
        "title": f"🔔 {type}: {offer.get('tytul', 'Ogłoszenie')}",
        "url": offer.get('link', ''),
        "color": color,
        "fields": [
            {"name": "Cena", "value": f"{offer.get('cena', '?')} zł", "inline": True},
            {"name": "Lokalizacja", "value": f"{offer.get('lokalizacja', '?')}", "inline": False}
        ],
        "footer": {"text": f"Bot RPi (Node {NODE_ID})"}
    }
    if "BAN" in type:
        embed['fields'] = [{"name": "Status", "value": "Wymagany reset IP"}]

    try:
        resp = requests.post(DISCORD_URL, json={"embeds": [embed]}, timeout=15)
        if resp.status_code in [200, 204]: return True
    except: pass
    return False

def as_str(val) -> str:
    if val is None: return ""
    if isinstance(val, dict):
        for key in ("label", "value", "fullName", "name", "text"):
            if key in val and val[key]: return as_str(val[key])
    if isinstance(val, (list, tuple, set)):
        parts = [as_str(v) for v in val if v not in (None, "")]
        return ", ".join([p for p in parts if p != ""])
    return str(val).strip()

def get_from_chars(chars, keys):
    for char in chars:
        if char.get('key') in keys:
            for field in ('localizedValue', 'valueLabel', 'value', 'formattedValue'):
                if char.get(field): return as_str(char[field])
    return ""

def get_from_target(target, keys):
    for key in keys:
        if key in target and target[key] not in (None, "", []):
            return as_str(target[key])
    return ""

def polish_floor(val: str) -> str:
    txt = (val or "").lower()
    if not txt: return ""
    if "parter" in txt or "ground" in txt: return "0"
    m = re.search(r"\d+", txt)
    return m.group(0) if m else ""

def translate_polish(value: str, mapping: dict) -> str:
    if not value: return ""
    lower = value.lower()
    return mapping.get(lower, value)

def clean_number(txt: str) -> str:
    if not txt: return ""
    m = re.search(r"[0-9]+(?:[\\.,][0-9]+)?", str(txt))
    return m.group(0).replace(',', '.') if m else ""

ANEKS_PATTERN = re.compile(r"\baneks\w*\b", re.IGNORECASE)
def detect_aneks_flag(*chunks) -> str:
    text = " ".join(as_str(chunk) for chunk in chunks if chunk not in (None, ""))
    return "TAK" if ANEKS_PATTERN.search(text) else "NIE"

def fill_defaults(rec: dict) -> dict:
    if not rec.get('powierzchnia') and rec.get('metraz'):
        rec['powierzchnia'] = rec['metraz']
    defaults = {
        'rok_budowy': 'brak', 'ogrzewanie': 'brak', 'kaucja': 'brak', 
        'stan': 'brak', 'czynsz': '0', 'pietro': 'brak', 'pokoje': 'brak', 
        'lokalizacja': 'brak', 'powierzchnia': 'brak', 'aneks': 'NIE',
    }
    for col, val in defaults.items():
        if rec.get(col) in ("", None): rec[col] = val
    return rec

def load_csv_safe(path):
    rows = []
    if not os.path.exists(path): return pd.DataFrame(columns=['data_pobrania','tytul','cena','metraz','link'])
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter=",", quotechar='"', escapechar='\\')
        for row in reader:
            if not row or len(row) < 3: continue
            if row[0].lower() == "data_pobrania": continue
            row = [c.strip() for c in row]
            link = row[-1]
            if not link.startswith("http"): continue
            data_pobrania = row[0]
            if len(row) >= 5:
                cena, metraz, tytul = row[-3], row[-2], ",".join(row[1:-3])
            else:
                tytul, cena, metraz = row[1], row[2], ""
            rows.append({'data_pobrania': data_pobrania, 'tytul': tytul, 'cena': cena, 'metraz': metraz, 'link': link})
    return pd.DataFrame(rows, columns=['data_pobrania','tytul','cena','metraz','link'])

# --- GŁÓWNA FUNKCJA POBIERAJĄCA ---
def get_full_details_json(url):
    try:
        sleep_time = random.uniform(45, 90)
        print(f"   (Czekam {sleep_time:.1f}s...)") 
        time.sleep(sleep_time)
        
        headers = {'User-Agent': ua.random, 'Accept-Language': 'pl-PL'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 403:
            print(f"🚨 CRITICAL: BAN IP (403) - {url}")
            send_discord_alert({'link': url, 'tytul': 'BAN IP'}, type="🚨 AWARIA BAN")
            time.sleep(120) 
            return None
        if resp.status_code == 429:
            print(f"⏳ WARN: Za szybko (429).")
            time.sleep(180)
            return None
        if resp.status_code != 200: return None

        soup = BeautifulSoup(resp.content, 'html.parser')
        if "Weryfikacja" in soup.title.text or "robot" in soup.text:
            print("🤖 CAPTCHA!")
            return None

        data_script = soup.find('script', id='__NEXT_DATA__')
        if not data_script: return None
        
        json_data = json.loads(data_script.string)
        page_props = json_data.get('props', {}).get('pageProps', {})
        ad_data = page_props.get('ad') or page_props.get('advertisement')
        if not ad_data: return None

        target = ad_data['target']
        chars = target.get('characteristics') or target.get('Characteristics') or []
        loc_obj = ad_data.get('location', {})
        addr = loc_obj.get('address', {})
        street = as_str(addr.get('street', '') or addr.get('route', ''))
        city = as_str(addr.get('cityWithDistrict') or addr.get('city') or "")
        lokalizacja = f"{street}, {city}".strip(", ")
        if not lokalizacja:
             breadcrumbs = loc_obj.get('geoLocation', {}).get('breadcrumbs', [])
             lokalizacja = ", ".join([as_str(b) for b in breadcrumbs])

        area_val = clean_number(get_from_target(target, ['Area', 'area']))
        desc = as_str(ad_data.get('description') or target.get('description'))
        title = as_str(ad_data.get('title') or target.get('title'))
        full_text = title + " " + desc + " " + " ".join([as_str(c.get('value')) for c in chars])

        return {
            'czynsz': get_from_chars(chars, {'rent', 'fee'}) or get_from_target(target, ['Rent', 'rent']),
            'pietro': polish_floor(get_from_chars(chars, {'floor_no', 'floor'}) or get_from_target(target, ['Floor_no', 'floor'])),
            'rok_budowy': get_from_chars(chars, {'build_year', 'year_built'}) or get_from_target(target, ['Build_year']),
            'ogrzewanie': translate_polish(get_from_chars(chars, {'heating'}) or get_from_target(target, ['Heating']), {"urban": "miejskie", "gas": "gazowe", "electric": "elektryczne"}),
            'kaucja': get_from_chars(chars, {'deposit', 'security_deposit'}) or get_from_target(target, ['Deposit']),
            'pokoje': get_from_target(target, ['Rooms_num', 'rooms']),
            'stan': translate_polish(get_from_chars(chars, {'construction_status', 'condition'}), {"ready_to_use": "do zamieszkania", "developer": "deweloperski"}),
            'lokalizacja': lokalizacja,
            'powierzchnia': area_val,
            'aneks': detect_aneks_flag(full_text),
            'data_aktualizacji': datetime.now().strftime("%Y-%m-%d")
        }
    except: return None

def main():
    print(f"--- START RPi PROCESSOR (History Protected) ---")

    # 1. Autoczyszczenie (ale BEZ zmiany wartości w komórkach!)
    clean_duplicates_in_master()

    dfs = []
    if os.path.exists(FILE_GH): dfs.append(load_csv_safe(FILE_GH))
    if os.path.exists(FILE_VPS): dfs.append(load_csv_safe(FILE_VPS))
    
    # Tworzenie pliku master jeśli nie istnieje
    if not os.path.exists(MASTER_FILE):
        pd.DataFrame(columns=FINAL_COLUMNS).to_csv(MASTER_FILE, index=False)

    if not dfs: return
    df_raw = pd.concat(dfs, ignore_index=True)
    
    # 2. Zbuduj bazę tego, co już mamy
    processed_keys = set()
    if os.path.exists(MASTER_FILE):
        try:
            # Wczytujemy z dtype=str żeby nic nie zmieniać
            df_m = pd.read_csv(MASTER_FILE, dtype=str)
            if 'link' in df_m.columns:
                processed_keys = set(df_m['link'].apply(dedupe_key_from_link))
        except: pass

    # 3. Wybierz TYLKO nowe (ignoruj wszystko co już jest w bazie)
    links_to_do = []
    for record in df_raw.to_dict('records'):
        key = dedupe_key_from_link(record['link'])
        
        # JEŚLI KLUCZ JUŻ ISTNIEJE W PLIKU - POMIŃ GO CAŁKOWICIE!
        # Nawet jeśli w pliku wejściowym są nowsze dane - historia wygrywa.
        if key not in processed_keys:
            links_to_do.append(record)
            processed_keys.add(key) 

    total = len(links_to_do)
    print(f"Do przetworzenia (netto): {total}")

    for i, row in enumerate(links_to_do):
        if i % TOTAL_NODES != NODE_ID: continue

        print(f"[{i+1}/{total}] {row['link'][-25:]}")
        details = get_full_details_json(row['link'])
        
        if details:
            full_record = {**row, **details}
            full_record = fill_defaults(full_record)
            
            # ZAPIS PANCERNY
            df_single = pd.DataFrame([full_record])
            for col in FINAL_COLUMNS:
                if col not in df_single.columns: df_single[col] = ""
            df_single = df_single[FINAL_COLUMNS]

            exists = os.path.exists(MASTER_FILE) and os.path.getsize(MASTER_FILE) > 0
            try:
                with open(MASTER_FILE, 'a', newline='', encoding='utf-8') as f:
                    df_single.to_csv(f, header=not exists, index=False)
                    f.flush()
                    os.fsync(f.fileno())
                print(f"   💾 Zapisano.")
                send_discord_alert(full_record)
            except Exception as e:
                print(f"⚠️ Błąd zapisu: {e}")

if __name__ == "__main__":
    main()