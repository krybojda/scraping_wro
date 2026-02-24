import os
import sys

# Próbujemy zaimportować Twoją oryginalną funkcję, która ładnie rysuje tabele!
try:
    from stats_readme import append_run_log
except ImportError:
    print("❌ Błąd: Nie znaleziono pliku stats_readme.py!")
    sys.exit(1)

# ==========================================
# 1. AKTUALIZACJA TABELI PROCESSORA
# ==========================================
if os.path.exists("temp_processor.txt"):
    try:
        with open("temp_processor.txt", "r", encoding="utf-8") as f:
            data = f.read().strip()
        
        if data:
            # Rozbijamy brudnopis: "23,23,OK,0/1"
            parts = data.split(',')
            if len(parts) >= 4:
                append_run_log(
                    component="processor",
                    found=int(parts[0]),
                    saved=int(parts[1]),
                    output_file="mieszkania_complete.csv",
                    status=parts[2],
                    node=parts[3]
                )
                print("✅ Statystyki Processora dodane do pięknej tabeli Markdown!")
            else:
                print("⚠️ Zły format danych w temp_processor.txt")
    except Exception as e:
        print(f"Błąd przy aktualizacji processora: {e}")

# ==========================================
# 2. AKTUALIZACJA TABELI SCRAPERA (Jeśli istnieje)
# ==========================================
if os.path.exists("temp_scraper.txt"):
    try:
        with open("temp_scraper.txt", "r", encoding="utf-8") as f:
            data = f.read().strip()
        
        if data:
            parts = data.split(',')
            if len(parts) >= 4:
                append_run_log(
                    component="scraper",
                    found=int(parts[0]),
                    saved=int(parts[1]),
                    output_file="mieszkania_vps.csv", # domyślny plik wyjściowy scrapera
                    status=parts[2],
                    node=parts[3]
                )
                print("✅ Statystyki Scrapera dodane do pięknej tabeli Markdown!")
            else:
                print("⚠️ Zły format danych w temp_scraper.txt")
    except Exception as e:
        print(f"Błąd przy aktualizacji scrapera: {e}")