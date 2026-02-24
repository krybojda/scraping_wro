import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import os
import json
import csv
import re
import sys
import signal  # <--- KLUCZOWA BIBLIOTEKA DO PKILL
from datetime import datetime
from fake_useragent import UserAgent

# --- KONFIGURACJA ---
FILE_GH = "mieszkania_gh.csv"
FILE_VPS = "mieszkania_vps.csv"

# Domyślne wartości (zostaną nadpisane przez config_local.py)
NODE_ID = 0
TOTAL_NODES = 1

# 1. Najpierw ładujemy config, żeby znać NODE_ID
if not os.path.exists("config_local.py"):
    with open("config_local.py", "w") as f: f.write(f"NODE_ID={NODE_ID}\nTOTAL_NODES={TOTAL_NODES}")

try: 
    from config_local import NODE_ID, TOTAL_NODES
except: 
    pass

print(f"🔧 Config: Node {NODE_ID} / {TOTAL_NODES}")

# 2. Dopiero teraz ustawiamy nazwy plików zależnie od trybu pracy
if TOTAL_NODES > 1:
    # Tryb KLASTRA (wiele maszyn) -> Każdy ma swój plik
    MASTER_FILE = f"mieszkania_node_{NODE_ID}.csv"
    BLACKLIST_FILE = f"blacklist_node_{NODE_ID}.csv"
    print(f"🤖 Tryb CLUSTER. Zapisuję do: {MASTER_FILE}")
else:
    # Tryb SOLO (jedna maszyna) -> Jeden główny plik
    MASTER_FILE = "mieszkania_complete.csv"
    BLACKLIST_FILE = "blacklist.csv"
    print(f"🤖 Tryb SOLO. Zapisuję do: {MASTER_FILE}")

DISCORD_URL = "https://discord.com/api/webhooks/1470223047867764800/m08l3piGAiD5sSXnl2bTgJX1LRzopi9WBjSkqUp5s9eXRuXR6o4exmVLChVdWRIIk_R2"

ua = UserAgent()

FINAL_COLUMNS = [
    'data_pobrania', 'tytul', 'cena', 'link', 'aneks', 
    'czynsz', 'pietro', 'pokoje', 'lokalizacja', 
    'rok_budowy', 'ogrzewanie', 'kaucja', 'stan', 
    'powierzchnia', 'data_aktualizacji'
]

STATS = {
    "checked": 0, "found": 0, "saved": 0, "skipped": 0, "captcha": 0, "ban": 0
}

# Flaga sterująca zatrzymaniem
stop_requested = False

# --- OBSŁUGA SYGNAŁÓW (pkill / Ctrl+C) ---
def signal_handler(signum, frame):
    global stop_requested
    print(f"\n🛑 OTRZYMANO SYGNAŁ ZATRZYMANIA ({signum})! Kończę bezpiecznie...")
    stop_requested = True

# Rejestrujemy obsługę sygnałów
signal.signal(signal.SIGTERM, signal_handler) # To łapie 'sudo pkill'
signal.signal(signal.SIGINT, signal_handler)  # To łapie 'Ctrl+C'

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

def send_discord_summary(manual_stop=False):
    """Wysyła raport końcowy na Discorda."""
    
    print("\n" + "="*40)
    print(f"📊 RAPORT KOŃCOWY (Node {NODE_ID})")
    if manual_stop or stop_requested: print("   🛑 STATUS: ZATRZYMANO RĘCZNIE (pkill/Ctrl+C)")
    print(f"   🔍 Sprawdzono:       {STATS.get('checked', 0)}")
    print(f"   💾 Zapisano nowych:  {STATS['saved']}")
    print(f"   ⚠️ Captcha / Ban:    {STATS['captcha']} / {STATS['ban']}")
    print(f"   🗑️ Pominięto:        {STATS['skipped']}")
    print("="*40 + "\n")

    if "TWOJ_ID" in DISCORD_URL: return
    
    ping_msg = ""
    if STATS['captcha'] > 0 or STATS['ban'] > 0:
        color = 15548997 # Czerwony
        title = "🚨 RPi RAPORT: AWARIA / BLOKADA"
        ping_msg = "@everyone 🆘 WYMAGANA INTERWENCJA!" 
    elif manual_stop or stop_requested:
        color = 16776960 # Żółty
        title = "🛑 RPi RAPORT: Zatrzymano ręcznie"
    elif STATS['saved'] > 0:
        color = 5814783  # Zielony
        title = "📊 RPi RAPORT: Sukces"
        ping_msg = "@here 👋 Znaleziono nowe oferty!"
    else:
        color = 12370112 # Szary
        title = "💤 RPi RAPORT: Brak nowości"

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
    payload = {"content": ping_msg, "embeds": [embed]}
    try: requests.post(DISCORD_URL, json=payload, timeout=10)
    except: pass

def send_discord_alert(offer, type="Nowa oferta"):
    if "TWOJ_ID" in DISCORD_URL: return False
    color = 5814783 if type == "Nowa oferta" else 15548997
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

def get_full_details_json(url):
    # --- PRZERYWANIE SPANIA PRZY PKILL ---
    # Zamiast jednego długiego sleepa, robimy pętlę krótkich sleepów
    # żeby szybciej zareagować na sygnał stopu
    sleep_target = random.uniform(45, 90)
    print(f"   (Czekam {sleep_target:.1f}s...)") 
    
    elapsed = 0
    while elapsed < sleep_target:
        if stop_requested:
            return None, "MANUAL_STOP" # Przerywamy czekanie natychmiast
        time.sleep(1)
        elapsed += 1

    try:
        headers = {'User-Agent': ua.random, 'Accept-Language': 'pl-PL'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 403: return None, "BAN"
        if resp.status_code == 429: return None, "RATE_LIMIT"
        if resp.status_code != 200: return None, "HTTP_ERROR"

        soup = BeautifulSoup(resp.content, 'html.parser')
        if "Weryfikacja" in soup.title.text or "robot" in soup.text:
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
            'pokoje': get_from_chars(chars, {'rooms_num', 'room'}) or get_from_target(target, ['Rooms_num', 'rooms']),
            'stan': translate_polish(
                get_from_chars(chars, {'construction_status', 'condition', 'finishing_state'}) or get_from_target(target, ['Condition', 'condition', 'finishing_state']), 
                {
                    "ready_to_use": "do zamieszkania", 
                    "developer": "deweloperski",
                    "to_renovation": "do remontu",
                    "to_completion": "do wykończenia"
                }
            ),
            'lokalizacja': lokalizacja,
            'powierzchnia': area_val,
            'aneks': detect_aneks_flag(full_text),
            'data_aktualizacji': datetime.now().strftime("%Y-%m-%d")
        }
        return result, "OK"
    except Exception as e:
        print(f"   ⚠️ Szczegóły błędu: {e}")
        return None, "ERROR"

def classify_processor_status(status_key: str) -> str:
    if status_key == "manual_stop":
        return "MANUAL_STOP"
    if status_key == "crash":
        return "CRASH"
    if status_key == "no_input":
        return "NO_INPUT"
    if STATS["captcha"] > 0 or STATS["ban"] > 0:
        return "BLOCKED"
    return "OK"

def main():
    print(f"--- START RPi PROCESSOR (Safety pkill ready) ---")
    clean_duplicates_in_master()
    run_status_key = "ok"

    dfs = []
    if os.path.exists(FILE_GH): dfs.append(load_csv_safe(FILE_GH))
    if os.path.exists(FILE_VPS): dfs.append(load_csv_safe(FILE_VPS))
    
    if not os.path.exists(MASTER_FILE):
        pd.DataFrame(columns=FINAL_COLUMNS).to_csv(MASTER_FILE, index=False)

    if not dfs:
        run_status_key = "no_input"
        print("Brak plikow wejsciowych.")
        send_discord_summary()
        try:
            aktualny_status = classify_processor_status(run_status_key)
            with open("temp_processor.txt", "w", encoding="utf-8") as f:
                f.write(f"{STATS['found']},{STATS['saved']},{aktualny_status},{NODE_ID}/{TOTAL_NODES}\n")
            print("📝 Utworzono brudnopis (temp_processor.txt) dla skryptu Bash.")
        except Exception as exc:
            print(f"⚠️ Błąd zapisu brudnopisu: {exc}")
        return

    df_raw = pd.concat(dfs, ignore_index=True)
    
    # --- WCZYTYWANIE HISTORII (POPRAWIONE) ---
    processed_keys = set()

    # 1. KROK PIERWSZY: Wczytaj Wielką Historię (mieszkania_complete.csv)
    # To jest kluczowe! Nawet jak piszemy do node_0.csv, musimy wiedzieć, co już jest w bazie.
    if os.path.exists("mieszkania_complete.csv"):
        try:
            # Wczytujemy tylko kolumnę link, żeby było szybciej
            df_global = pd.read_csv("mieszkania_complete.csv", usecols=['link'], dtype=str, on_bad_lines='skip')
            if 'link' in df_global.columns:
                global_links = set(df_global['link'].apply(dedupe_key_from_link))
                processed_keys.update(global_links)
                print(f"📚 Załadowano bazę główną (complete): {len(global_links)} ofert.")
        except Exception as e:
            print(f"⚠️ Nie udało się wczytać bazy głównej: {e}")

    # 2. KROK DRUGI: Wczytaj Lokalną Pracę (mieszkania_node_X.csv)
    # Jeśli plik docelowy jest inny niż główny (tryb klastra), wczytaj też to, co w nim już jest.
    if MASTER_FILE != "mieszkania_complete.csv" and os.path.exists(MASTER_FILE):
        try:
            df_local = pd.read_csv(MASTER_FILE, usecols=['link'], dtype=str, on_bad_lines='skip')
            if 'link' in df_local.columns:
                local_links = set(df_local['link'].apply(dedupe_key_from_link))
                processed_keys.update(local_links)
                print(f"📝 Załadowano plik roboczy ({MASTER_FILE}): {len(local_links)} ofert.")
        except Exception as e:
            print(f"⚠️ Nie udało się wczytać pliku roboczego: {e}")

    print(f"🧠 ŁĄCZNA PAMIĘĆ BOTA: {len(processed_keys)} unikalnych ofert (nie będę ich sprawdzał).")
    # -----------------------------------------

# --- WCZYTYWANIE CZARNEJ LISTY (POPRAWIONE) ---
    blacklisted_keys = set()
    
    # 1. Zawsze wczytaj główną, starą blacklistę (jeśli istnieje)
    # Dzięki temu Node wie o banach z przeszłości
    if os.path.exists("blacklist.csv"):
        try:
            with open("blacklist.csv", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        blacklisted_keys.add(dedupe_key_from_link(line.strip()))
            print(f"⚫ Załadowano główną blacklist.csv: {len(blacklisted_keys)} wpisów.")
        except: pass

    # 2. Jeśli pracujemy w klastrze, wczytaj też plik lokalny tego Node'a
    # (bo może przed chwilą coś zbanował, a nie scaliłeś jeszcze plików)
    if TOTAL_NODES > 1 and os.path.exists(BLACKLIST_FILE) and BLACKLIST_FILE != "blacklist.csv":
        try:
            local_count = 0
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        key = dedupe_key_from_link(line.strip())
                        if key not in blacklisted_keys:
                            blacklisted_keys.add(key)
                            local_count += 1
            print(f"⚫ Dociągnięto z {BLACKLIST_FILE}: {local_count} nowych wpisów.")
        except: pass
    
    print(f"⚫ ŁĄCZNIE NA CZARNEJ LIŚCIE: {len(blacklisted_keys)}")
    # ---------------------------------------------

    links_to_do = []
    for record in df_raw.to_dict('records'):
        key = dedupe_key_from_link(record['link'])
        if key not in processed_keys and key not in blacklisted_keys:
            links_to_do.append(record)
            processed_keys.add(key)

    total = len(links_to_do)
    print(f"Do przetworzenia (netto): {total}")
    assigned_total = sum(1 for idx in range(total) if idx % TOTAL_NODES == NODE_ID)
    STATS['found'] = total
    STATS['checked'] = assigned_total
    print(f"Do sprawdzenia na tym nodzie: {assigned_total}")

    try:
        # --- NOWE: Ustawienie licznika błędów ---
        consecutive_fails = 0
        MAX_FAILS = 5
        for i, row in enumerate(links_to_do):
            # SPRAWDZAMY FLAGĘ NA POCZĄTKU KAŻDEGO OBIEGU
            if stop_requested:
                run_status_key = "manual_stop"
                break
            
            if i % TOTAL_NODES != NODE_ID: continue

            print(f"[{i+1}/{total}] {row['link'][-35:]}")
            details, status = get_full_details_json(row['link'])
            
            # Jeśli przerwano podczas sleepa:
            if status == "MANUAL_STOP":
                run_status_key = "manual_stop"
                break

            if status == "OK" and details:
                consecutive_fails = 0
                full_record = {**row, **details}
                full_record = fill_defaults(full_record)
                
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
                    STATS['saved'] += 1
                except Exception as e:
                    print(f"   ⚠️ Błąd zapisu: {e}")

            elif status == "CAPTCHA":
                print(f"   🤖 POMINIĘTO: Wykryto CAPTCHA!")
                STATS['captcha'] += 1
                
                # --- NOWE: Dolicz błąd i sprawdź limit ---
                consecutive_fails += 1
                if consecutive_fails >= MAX_FAILS:
                    print(f"\n🛑 HAMULEC AWARYJNY: {consecutive_fails} błędów pod rząd. Zamykam Node'a!")
                    break
                # -----------------------------------------

            elif status == "BAN":
                print(f"   🚨 POMINIĘTO: BAN IP (403)!")
                STATS['ban'] += 1
                
                # --- NOWE: Dolicz błąd i sprawdź limit ---
                consecutive_fails += 1
                if consecutive_fails >= MAX_FAILS:
                    print(f"\n🛑 HAMULEC AWARYJNY: {consecutive_fails} banów pod rząd. Zamykam Node'a!")
                    break
                # -----------------------------------------

            elif status == "RATE_LIMIT":
                print(f"   ⏳ POMINIĘTO: Rate Limit (429)!")
                time.sleep(180)
                
            else:
                print(f"   ⚠️ POMINIĘTO: {status} (-> Blacklist)")
                STATS['skipped'] += 1
                try:
                    with open(BLACKLIST_FILE, "a", encoding="utf-8") as f:
                        f.write(row['link'] + "\n")
                except: pass

    except Exception as e:
        print(f"!!! KRYTYCZNY BŁĄD PĘTLI: {e}")
        run_status_key = "crash"
    finally:
        # TO WYKONA SIĘ ZAWSZE - NAWET PO PKILL
        print("--- Koniec pracy. Wysyłam raport... ---")
        if stop_requested and run_status_key == "ok":
            run_status_key = "manual_stop"

        run_status = classify_processor_status(run_status_key)
        send_discord_summary(manual_stop=(run_status == "MANUAL_STOP"))

        try:
            with open("temp_processor.txt", "w", encoding="utf-8") as f:
                f.write(f"{STATS['found']},{STATS['saved']},{run_status},{NODE_ID}/{TOTAL_NODES}\n")
            print("📝 Utworzono brudnopis (temp_processor.txt) dla skryptu Bash.")
        except Exception as exc:
            print(f"⚠️ Błąd zapisu brudnopisu: {exc}")

if __name__ == "__main__":
    main()
