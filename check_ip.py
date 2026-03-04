import sys
import time
import socket

# --- SPRAWDZANIE CZY BIBLIOTEKA JEST ZAINSTALOWANA ---
try:
    import cloudscraper
except ImportError:
    print("❌ BŁĄD: Brak biblioteki 'cloudscraper'.")
    print("👉 Wpisz: pip3 install cloudscraper")
    sys.exit(1)

# --- KOLORY ---
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_otodom_status():
    print(f"\n3. 🏠 DIAGNOSTYKA OTODOM (Wersja Cloudscraper)...")
    url = "https://www.otodom.pl/pl/oferty/sprzedaz/mieszkanie/wroclaw"
    
    # Tworzymy scrapera, który udaje Chrome
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'linux', 'desktop': True})

    try:
        print(f"   Łączę się z: {url[:30]}...")
        start = time.time()
        
        # Używamy scraper.get zamiast requests.get
        resp = scraper.get(url, timeout=15)
        duration = time.time() - start
        
        print(f"   Czas: {duration:.2f}s | Kod: {resp.status_code}")

        if resp.status_code == 200:
            # Cloudscraper powinien sam rozwiązać captchę. 
            # Jeśli nadal widzimy "Weryfikacja", to znaczy, że Cloudflare jest b. agresywny.
            if "Weryfikacja" in resp.text or "Just a moment" in resp.text:
                print(f"   [{RED}INFO{RESET}] 🤖 Nadal widzę ekran weryfikacji.")
                print("   Cloudflare wymaga pełnej przeglądarki (Selenium).")
            else:
                print(f"   [{GREEN}SUKCES{RESET}] ✅ Przebiliśmy się przez Cloudflare!")
                print(f"   Tytuł strony: {resp.text.split('<title>')[1].split('</title>')[0][:50]}...")
        
        elif resp.status_code == 403:
            print(f"   [{RED}ZŁE WIEŚCI{RESET}] 🚨 403 Forbidden - Mimo scrapera.")
        else:
            print(f"   [{YELLOW}INFO{RESET}] Kod: {resp.status_code}")

    except Exception as e:
        print(f"   [{RED}BŁĄD{RESET}] {e}")

def main():
    print("--- 🩺 DOCTOR V3 (Cloudscraper) ---")
    check_otodom_status()
    print("\n--- KONIEC ---")

if __name__ == "__main__":
    main()