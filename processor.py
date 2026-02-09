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

# !!! TUTAJ WKLEJ SWÓJ LINK Z DISCORDA !!!
DISCORD_URL = "https://discord.com/api/webhooks/1470223047867764800/m08l3piGAiD5sSXnl2bTgJX1LRzopi9WBjSkqUp5s9eXRuXR6o4exmVLChVdWRIIk_R2"



ua = UserAgent()
  

  
# Definiujemy stałą kolejność kolumn w pliku, żeby nic się nie przesuwało
FINAL_COLUMNS = [
    'data_pobrania', 'tytul', 'cena', 'link', 'metraz', 
    'czynsz', 'pietro', 'pokoje', 'lokalizacja', 
    'rok_budowy', 'ogrzewanie', 'kaucja', 'stan', 
    'powierzchnia', 'data_aktualizacji'
]

def send_discord_alert(offer, type="Nowa oferta"):
    if "TWOJ_ID" in DISCORD_URL: return 
    color = 5814783 if type == "Nowa oferta" else 16776960
    embed = {
        "title": f"🏠 {type}: {offer.get('tytul', 'Ogłoszenie')}",
        "url": offer['link'],
        "color": color, 
        "fields": [
            {"name": "Cena", "value": f"{offer.get('cena', '?')} zł", "inline": True},
            {"name": "Czynsz", "value": f"{offer.get('czynsz', '?')}", "inline": True},
            {"name": "Lokalizacja", "value": f"{offer.get('lokalizacja', '?')}", "inline": False}
        ],
        "footer": {"text": "Bot Nieruchomości RPi"}
    }
    try:
        requests.post(DISCORD_URL, json={"embeds": [embed]})
    except: pass

def as_str(val) -> str:
    """Safely convert various API values (dict/list/primitive) to string."""
    if val is None:
        return ""
    # unwrap dicts with common text keys
    if isinstance(val, dict):
        for key in ("label", "value", "fullName", "name", "text"):
            if key in val and val[key]:
                return as_str(val[key])
    if isinstance(val, (list, tuple, set)):
        parts = [as_str(v) for v in val if v not in (None, "")]
        return ", ".join([p for p in parts if p != ""])
    return str(val).strip()

def normalize_value(val):
    """Backward-compat shim: use as_str for normalization."""
    return as_str(val)

def get_from_chars(chars, keys):
    """Read characteristic list (otodom) in a case-insensitive way."""
    for char in chars:
        if char.get('key') in keys:
            for field in ('localizedValue', 'valueLabel', 'value', 'formattedValue'):
                if char.get(field):
                    return as_str(char[field])
    return ""

def get_from_target(target, keys):
    """Fallback: direct lookup in target dict."""
    for key in keys:
        if key in target and target[key] not in (None, "", []):
            return as_str(target[key])
    return ""

def polish_floor(val: str) -> str:
    txt = (val or "").lower()
    if not txt:
        return ""
    if "parter" in txt or "ground" in txt:
        return "0"
    import re
    m = re.search(r"\d+", txt)
    return m.group(0) if m else ""

def translate_polish(value: str, mapping: dict) -> str:
    if not value:
        return ""
    lower = value.lower()
    if lower in mapping:
        return mapping[lower]
    return value  # assume already PL

def clean_number(txt: str) -> str:
    """Pick out first numeric part (e.g., '45 m²' -> '45')."""
    if not txt:
        return ""
    import re
    m = re.search(r"[0-9]+(?:[\\.,][0-9]+)?", str(txt))
    return m.group(0).replace(',', '.') if m else ""

def loc_to_str(loc) -> str:
    return as_str(loc)

def load_csv_safe(path):
    """Robust reader: 5 kolumn (data, tytul, cena, metraz, link) nawet gdy tytuł ma nie-quoted przecinki."""
    rows = []
    stats = {"total": 0, "kept": 0, "skip_no_link": 0, "skip_short": 0}

    if not os.path.exists(path):
        return pd.DataFrame(columns=['data_pobrania','tytul','cena','metraz','link'])

    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter=",", quotechar='"', escapechar='\\')
        for row in reader:
            stats["total"] += 1
            if not row or all(not c.strip() for c in row):
                stats["skip_short"] += 1
                continue
            if row[0].strip().lower() == "data_pobrania":
                continue
            row = [c.strip() for c in row]

            link = row[-1] if row else ""
            if not link.startswith("http"):
                stats["skip_no_link"] += 1
                continue

            if len(row) >= 5:
                data_pobrania = row[0]
                cena = row[-3]
                metraz = row[-2]
                tytul = ",".join(row[1:-3]) if len(row) > 5 else row[1]
            elif len(row) == 4:
                data_pobrania, tytul, cena = row[0], row[1], row[2]
                metraz = ""
            elif len(row) == 3:
                data_pobrania, tytul = row[0], row[1]
                cena, metraz = row[2], ""
            else:
                stats["skip_short"] += 1
                continue

            rows.append({
                'data_pobrania': data_pobrania,
                'tytul': tytul,
                'cena': cena,
                'metraz': metraz,
                'link': link
            })
            stats["kept"] += 1

    print(f"[{os.path.basename(path)}] total_lines={stats['total']} kept={stats['kept']} skip_no_link={stats['skip_no_link']} skip_short={stats['skip_short']}")
    return pd.DataFrame(rows, columns=['data_pobrania','tytul','cena','metraz','link'])

def get_full_details_json(url):
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

        chars = target.get('characteristics') or target.get('Characteristics') or []

        loc_obj = ad_data.get('location', {})
        geo = loc_obj.get('geoLocation') or loc_obj.get('address') or {}
        breadcrumbs = geo.get('breadcrumbs') or []
        addr = loc_obj.get('address', {})
        street = as_str(addr.get('street', '') or addr.get('route', ''))
        number = as_str(addr.get('streetNumber', '') or addr.get('street_number', ''))
        city = as_str(addr.get('cityWithDistrict') or addr.get('city') or addr.get('region') or "")

        addr_str = " ".join([street, number]).strip()
        if city:
            addr_str = (addr_str + ", " + city).strip(", ")

        if addr_str:
            lokalizacja = addr_str
        else:
            loc_parts = []
            for loc in breadcrumbs:
                s = loc_to_str(loc)
                if s:
                    loc_parts.append(str(s))
            lokalizacja = ", ".join(loc_parts)

        area_val = clean_number(get_from_target(target, ['Area', 'area']))

        return {
            'czynsz': get_from_chars(chars, {'rent', 'fee'}) or get_from_target(target, ['Rent', 'rent', 'estateRent']),
            'pietro': polish_floor(get_from_chars(chars, {'floor_no', 'floor'}) or get_from_target(target, ['Floor_no', 'floor_no', 'floor'])),
            'rok_budowy': get_from_chars(chars, {'build_year', 'year_built'}) or get_from_target(target, ['Build_year', 'build_year']),
            'ogrzewanie': translate_polish(
                get_from_chars(chars, {'heating'}) or get_from_target(target, ['Heating', 'heating']),
                {
                    "central heating": "centralne",
                    "district heating": "miejskie",
                    "gas": "gazowe",
                    "electric": "elektryczne",
                    "oil": "olejowe",
                    "coal": "węglowe",
                    "other": "inne",
                },
            ),
            'kaucja': get_from_chars(chars, {'deposit', 'security', 'security_deposit', 'security_security'}) or get_from_target(target, ['Deposit', 'security_deposit', 'security_security']),
            'pokoje': get_from_target(target, ['Rooms_num', 'rooms']),
            'stan': translate_polish(
                get_from_chars(chars, {'construction_status', 'condition', 'state'}) or get_from_target(target, ['Construction_status', 'construction_status', 'condition', 'state']),
                {
                    "ready to move in": "do zamieszkania",
                    "do zamieszkania": "do zamieszkania",
                    "developer's standard": "deweloperski",
                    "developer standard": "deweloperski",
                    "very good": "bardzo dobry",
                    "good": "dobry",
                    "after renovation": "po remoncie",
                    "to renovate": "do remontu",
                    "to refresh": "do odświeżenia",
                    "shell condition": "stan surowy",
                },
            ),
            'lokalizacja': lokalizacja,
            'powierzchnia': area_val,
            'data_aktualizacji': datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"Błąd przy {url}: {e}")
        return None

def main():
    print("--- START RPi PROCESSOR (Naprawiona Kolejność) ---")

    dfs = []
    if os.path.exists(FILE_GH): 
        try: dfs.append(load_csv_safe(FILE_GH))
        except Exception as e: 
            print(f"Nie mogę wczytać {FILE_GH}: {e}")
    if os.path.exists(FILE_VPS): 
        try: dfs.append(load_csv_safe(FILE_VPS))
        except Exception as e:
            print(f"Nie mogę wczytać {FILE_VPS}: {e}")
    
    # Upewnij się, że MASTER_FILE istnieje (pusty z nagłówkiem), żeby git add nie wywalał się przy braku ofert
    if not os.path.exists(MASTER_FILE):
        pd.DataFrame(columns=FINAL_COLUMNS).to_csv(MASTER_FILE, index=False)

    if not dfs: return

    df_raw = pd.concat(dfs, ignore_index=True)
    # ustaw kolejność: najnowsze rekordy na końcu, żeby brać najświeższą cenę per link
    if 'data_pobrania' in df_raw.columns:
        df_raw['__ts'] = pd.to_datetime(df_raw['data_pobrania'], errors='coerce')
        df_raw = df_raw.sort_values('__ts')
    df_unique = df_raw.drop_duplicates(subset='link', keep='last')
    if '__ts' in df_unique.columns:
        df_unique = df_unique.drop(columns='__ts')

    processed_prices = {}
    if os.path.exists(MASTER_FILE):
        try:
            df_master = pd.read_csv(MASTER_FILE)
            if 'link' in df_master.columns and 'cena' in df_master.columns:
                processed_prices = pd.Series(df_master.cena.values, index=df_master.link).to_dict()
        except: pass

    links_to_do = []
    for record in df_unique.to_dict('records'):
        link = record['link']
        new_price = str(record.get('cena', '')).strip()
        
        if link not in processed_prices:
            record['typ_akcji'] = "NOWE"
            links_to_do.append(record)
        else:
            old_price = str(processed_prices[link]).strip()
            np_clean = new_price.replace(' ', '').replace('zł', '')
            op_clean = old_price.replace(' ', '').replace('zł', '')
            if np_clean != op_clean and np_clean and op_clean:
                record['typ_akcji'] = "ZMIANA CENY"
                links_to_do.append(record)

    total = len(links_to_do)
    print(f"Do przetworzenia: {total}")

    new_records = []
    for i, row in enumerate(links_to_do):
        print(f"[{i+1}/{total}] {row['link'][-20:]}")
        details = get_full_details_json(row['link'])
        
        if details:
            full_record = {**row, **details}
            # Nie duplikuj metrażu: jeśli powierzchnia = metraż, zostaw tylko metraż
            try:
                metraz_val = clean_number(full_record.get('metraz', ''))
                pow_val = clean_number(full_record.get('powierzchnia', ''))
                if metraz_val and pow_val and metraz_val == pow_val:
                    full_record['powierzchnia'] = ""
            except:
                pass
            new_records.append(full_record)
            try:
                msg_type = "Nowa oferta" if row.get('typ_akcji') == "NOWE" else "📉 Zmiana ceny"
                send_discord_alert(full_record, type=msg_type)
            except: pass
        
        # ZAPIS Z FILTROWANIEM KOLUMN
        if new_records:
            df_new = pd.DataFrame(new_records)
            # 1. Usuń kolumnę pomocniczą typ_akcji, żeby nie psuła pliku
            if 'typ_akcji' in df_new.columns:
                df_new = df_new.drop(columns=['typ_akcji'])
            
            # 2. Uzupełnij brakujące kolumny (jeśli jakiejś brakuje)
            for col in FINAL_COLUMNS:
                if col not in df_new.columns:
                    df_new[col] = ""

            # 3. Posortuj kolumny wg ustalonej kolejności
            df_new = df_new[FINAL_COLUMNS]

            exists = os.path.exists(MASTER_FILE)
            df_new.to_csv(MASTER_FILE, mode='a', header=not exists, index=False)
            new_records = []

if __name__ == "__main__":
    main()
