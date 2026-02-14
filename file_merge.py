import pandas as pd
import glob
import os

# --- KONFIGURACJA ---
MASTER_FILE = "mieszkania_complete.csv"
BLACKLIST_FILE = "blacklist.csv"

# Pliki, których NIE CHCEMY scalać (surowe dane, kopie robocze itp.)
EXCLUDED_FILES = [
    "mieszkania_gh.csv",
    "mieszkania_vps.csv",
    "mieszkania_complete_backup.csv" # Opcjonalnie, dla bezpieczeństwa
]

def merge_housing():
    print(f"\n🏠 --- SCALANIE (TRYB DOKLEJANIA + FILTROWANIE) ---")

    # 1. Wczytujemy plik GŁÓWNY (Baza, której nie ruszamy)
    if os.path.exists(MASTER_FILE):
        try:
            df_master = pd.read_csv(MASTER_FILE, sep=None, engine='python', on_bad_lines='skip')
            df_master.columns = df_master.columns.str.strip()
            print(f"✅ Wczytano bazę główną: {len(df_master)} rekordów.")
        except Exception as e:
            print(f"❌ Błąd bazy głównej: {e}")
            df_master = pd.DataFrame()
    else:
        print("ℹ️  Brak pliku głównego - zostanie utworzony nowy.")
        df_master = pd.DataFrame()

    # 2. Szukamy plików do DOKLEJENIA (Node'y)
    all_files = glob.glob("mieszkania_*.csv")
    
    files_to_merge = []
    for f in all_files:
        # --- FILTRY WYKLUCZAJĄCE ---
        if f == MASTER_FILE: continue           # Nie wczytuj samego siebie
        if "merged" in f: continue              # Nie wczytuj plików wynikowych
        if f in EXCLUDED_FILES:                 # <--- TU JEST TWOJA ZMIANA
            print(f"🚫 Ignoruję plik surowy: {f}")
            continue
        
        files_to_merge.append(f)

    if not files_to_merge:
        print("⚠️  Nie znaleziono odpowiednich plików (node_*) do doklejenia.")
        return

    print(f"📂 Wybrano {len(files_to_merge)} plików do przetworzenia.")

    new_data_frames = []
    for f in files_to_merge:
        try:
            df = pd.read_csv(f, sep=None, engine='python', on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            if 'link' in df.columns:
                new_data_frames.append(df)
                print(f"   ➕ Wczytano: {f} ({len(df)} ofert)")
        except:
            pass

    if new_data_frames:
        # Łączymy nowe pliki ze sobą
        df_new = pd.concat(new_data_frames, ignore_index=True)

        # 3. Sortujemy NOWE rekordy chronologicznie (najstarsze -> najnowsze)
        if 'data_pobrania' in df_new.columns:
            df_new['dt_temp'] = pd.to_datetime(df_new['data_pobrania'], errors='coerce')
            df_new = df_new.sort_values(by='dt_temp', ascending=True)
            df_new = df_new.drop(columns=['dt_temp'])

        # 4. DOKLEJAMY (Master na górze, Nowe na dole)
        full_df = pd.concat([df_master, df_new], ignore_index=True)

        # 5. USUWANIE DUPLIKATÓW
        # keep='first' -> Zostawia wersję z Mastera (górną).
        # subset=['link'] -> Jeśli link się powtarza, to duplikat (niezależnie od ceny).
        if 'link' in full_df.columns:
            before = len(full_df)
            full_df = full_df.drop_duplicates(subset=['link'], keep='first')
            print(f"✂️  Odrzucono duplikaty: {before - len(full_df)}")

        # Zapis
        full_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
        print(f"💾 ZAPISANO: {MASTER_FILE} (Razem: {len(full_df)} ofert)")

    else:
        print("❌ Brak poprawnych danych w nowych plikach.")

def merge_blacklist():
    print(f"\n⚫ --- SCALANIE BLACKLIST ---")
    
    # Wczytaj główną blacklistę
    existing_links = set()
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if "http" in line: existing_links.add(line.strip())
            print(f"✅ Baza blacklist: {len(existing_links)} wpisów.")
        except: pass

    # Szukaj plików blacklist*.csv (z wyłączeniem głównego)
    files = glob.glob("blacklist*.csv")
    files = [f for f in files if f != BLACKLIST_FILE]
    
    added_count = 0
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                for line in file:
                    clean = line.strip().replace('"', '')
                    if "http" in clean and clean not in existing_links:
                        existing_links.add(clean)
                        added_count += 1
        except: pass

    if existing_links:
        df = pd.DataFrame(list(existing_links), columns=['link'])
        df.to_csv(BLACKLIST_FILE, index=False, encoding='utf-8-sig')
        print(f"💾 ZAPISANO: {BLACKLIST_FILE} (Dodano nowych: {added_count})")

if __name__ == "__main__":
    merge_housing()
    merge_blacklist()
    input("\nNaciśnij ENTER, aby zakończyć...")