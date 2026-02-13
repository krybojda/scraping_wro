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

# Konfiguracja maszyny (dla rozproszonego przetwarzania)    
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

# --- LICZNIK STATYSTYK (NOWOŚĆ) ---
STATS = {
    "checked": 0,   # Ile linków przetworzono
    "saved": 0,     # Ile zapisano do pliku
    "skipped": 0,   # Ile pominięto (brak danych/stare)
    "captcha": 0,   # Ile razy wykryto weryfikację
    "ban": 0        # Ile razy 403
}

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
        df = pd.read_csv(MASTER_FILE, dtype=str)
        if 'link' not in df.columns: return
        initial_len = len(df)
        df['dedupe_key'] = df['link'].apply(dedupe_key_from_link)
        df = df.drop_duplicates(subset=['dedupe_key'], keep='last')
        df = df.drop(columns=['dedupe_key'])
        if initial_len != len(df):
            print(f"🧹 AUTOCZYSZCZENIE: Usunięto {initial_len - len(df)} duplikatów.")
            df.to_csv(MASTER_FILE, index=False)
    except Exception: pass

def send_discord_summary():
    """Wysyła raport końcowy na Discorda ORAZ zapisuje go w logach."""
    
    # --- CZĘŚĆ 1: ZAPIS DO LOGÓW ---
    print("\n" + "="*40)
    print(f"📊 RAPORT KOŃCOWY (Node {NODE_ID})")
    print(f"   🔍 Sprawdzono łącznie: {STATS.get('checked', 0)}")
    print(f"   💾 Zapisano nowych:    {STATS['saved']}")
    print(f"   ⚠️ Captcha / Ban:      {STATS['captcha']} / {STATS['ban']}")
    print(f"   🗑️ Pominięto:          {STATS['skipped']}")
    print("="*40 + "\n")
    # -------------------------------

    if "TWOJ_ID" in DISCORD_URL: return
    
    # --- CZĘŚĆ 2: LOGIKA POWIADOMIEŃ (PING) ---
    ping_msg = ""
    
    # Scenariusz 1: AWARIA (Ban/Captcha) -> Budzimy wszystkich!
    if STATS['captcha'] > 0 or STATS['ban'] > 0:
        color = 15548997 # Czerwony
        title = "🚨 RPi RAPORT: WYKRYTO PROBLEMY"
        ping_msg = "@everyone 🆘 WYMAGANA INTERWENCJA!" 

    # Scenariusz 2: SUKCES (Są nowe mieszkania) -> Wołamy obecnych
    elif STATS['saved'] > 0:
        color = 5814783  # Zielony
        title = "📊 RPi RAPORT: Sukces"
        ping_msg = "@here 👋 Znaleziono nowe oferty!"

    # Scenariusz 3: CISZA (Nic nowego) -> Bez pinga
    else:
        color = 12370112 # Szary
        title = "💤 RPi RAPORT: Brak nowości"
        ping_msg = "" # Pusty ciąg = brak powiadomienia

    embed = {
        "title": title,
        "color": color,
        "fields": [
            {"name": "🔍 Sprawdzono", "value": str(STATS.get('checked', 0)), "inline": True},
            {"name": "💾 Zapisano", "value": str(STATS['saved']), "inline": True},
            {"name": "⚠️ Captcha/Ban", "value": f"{STATS['captcha']} / {STATS['ban']}", "inline": True},
            {"name": "🗑️ Pominięto", "value": str(STATS['skipped']), "inline": True}
        ],
        "footer": {"text": f"Node {NODE_ID} • {datetime.now().strftime('%H:%M')}"}
    }

    # Budujemy paczkę z treścią (content) i ramką (embed)
    payload = {
        "content": ping_msg,  # <--- TUTAJ JEST MAGIA PINGOWANIA
        "embeds": [embed]
    }

    try: requests.post(DISCORD_URL, json=payload, timeout=10)
    except: pass

def send_discord_alert(offer, type="Nowa oferta"):
    if "TWOJ_ID" in DISCORD_URL: return False
    color = 5814783 if type == "Nowa oferta" else 15548997 if "BAN" in type else 16776960
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
    try: requests.post(DISCORD_URL, json={"embeds": [embed]}, timeout=15)
    except: pass

# ... (Funkcje parsujące bez zmian: as_str, get_from_chars itp.) ...
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

# --- GŁÓWNA FUNKCJA POBIERAJĄCA (Zwraca (dane, status)) ---
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
            return None, "BAN" # Zwracamy status
            
        if resp.status_code == 429:
            print(f"⏳ WARN: Za szybko (429).")
            time.sleep(180)
            return None, "RATE_LIMIT"

        if resp.status_code != 200: 
            return None, "HTTP_ERROR"

        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # WYKRYWANIE CAPTCHA
        if "Weryfikacja" in soup.title.text or "robot" in soup.text:
            print("🤖 CAPTCHA!")
            send_discord_alert({'link': url, 'tytul': 'CAPTCHA'}, type="🚨 AWARIA CAPTCHA")
            return None, "CAPTCHA"

        data_script = soup.find('script', id='__NEXT_DATA__')
        if not data_script: return None, "NO_JSON"
        
        json_data = json.loads(data_script.string)
        page_props = json_data.get('props', {}).get('pageProps', {})
        ad_data = page_props.get('ad') or page_props.get('advertisement')
        if not ad_data: return None, "EMPTY_DATA"

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

        result = {
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
        return result, "OK"
    except Exception as e:
        print(f"Error: {e}")
        return None, "ERROR"

def main():
    print(f"--- START RPi PROCESSOR (With Summary) ---")
    clean_duplicates_in_master()

    dfs = []
    if os.path.exists(FILE_GH): dfs.append(load_csv_safe(FILE_GH))
    if os.path.exists(FILE_VPS): dfs.append(load_csv_safe(FILE_VPS))
    
    if not os.path.exists(MASTER_FILE):
        pd.DataFrame(columns=FINAL_COLUMNS).to_csv(MASTER_FILE, index=False)

    if not dfs: 
        print("Brak plików wejściowych.")
        send_discord_summary() # Wyślij raport nawet jak pusto
        return

    df_raw = pd.concat(dfs, ignore_index=True)
    
    processed_keys = set()
    if os.path.exists(MASTER_FILE):
        try:
            df_m = pd.read_csv(MASTER_FILE, dtype=str)
            if 'link' in df_m.columns:
                processed_keys = set(df_m['link'].apply(dedupe_key_from_link))
        except: pass

    links_to_do = []
    for record in df_raw.to_dict('records'):
        key = dedupe_key_from_link(record['link'])
        if key not in processed_keys:
            links_to_do.append(record)
            processed_keys.add(key) 

    total = len(links_to_do)
    print(f"Do przetworzenia (netto): {total}")
    STATS['checked'] = total # Ustawiamy ile planujemy sprawdzić

    for i, row in enumerate(links_to_do):
        if i % TOTAL_NODES != NODE_ID: continue

        # 1. Wypisz numer i link
        print(f"[{i+1}/{total}] {row['link'][-35:]}")
        
        # 2. Pobierz dane
        details, status = get_full_details_json(row['link'])
        
        # 3. Zaloguj wynik
        if status == "OK" and details:
            full_record = {**row, **details}
            full_record = fill_defaults(full_record)
            
            # ZAPIS
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
                print(f"   💾 Zapisano.") # LOG: SUKCES
                send_discord_alert(full_record)
                STATS['saved'] += 1
            except Exception as e:
                print(f"   ⚠️ Błąd zapisu: {e}") # LOG: BŁĄD DYSKU
        
        elif status == "CAPTCHA":
            print(f"   🤖 POMINIĘTO: Wykryto CAPTCHA!") # LOG: CAPTCHA
            STATS['captcha'] += 1
            
        elif status == "BAN":
            print(f"   🚨 POMINIĘTO: BAN IP (403)!") # LOG: BAN
            STATS['ban'] += 1
            
        elif status == "RATE_LIMIT":
            print(f"   ⏳ POMINIĘTO: Rate Limit (429)!") # LOG: ZA SZYBKO
            
        else:
            # Inne powody: EMPTY_DATA, HTTP_ERROR, NO_JSON
            print(f"   ⚠️ POMINIĘTO: {status}") # LOG: INNE
            STATS['skipped'] += 1

    # NA SAM KONIEC: Wyślij raport zbiorczy
    print("--- Koniec pracy. Wysyłam raport... ---")
    send_discord_summary()

if __name__ == "__main__":
    main()