import sys
import time
import socket

# --- SPRAWDZANIE CZY BIBLIOTEKA JEST ZAINSTALOWANA ---
try:
    import requests
except ImportError:
    print("❌ BŁĄD KRYTYCZNY: Brak biblioteki 'requests'.")
    print("👉 Wpisz w terminalu: pip3 install requests")
    sys.exit(1)

# --- KOLORY ---
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_internet():
    print(f"\n1. 🌐 TEST INTERNETU (Ping Google DNS)...")
    try:
        # Próba połączenia z 8.8.8.8 na porcie 53 (DNS)
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        print(f"   [{GREEN}OK{RESET}] Połączenie działa.")
        return True
    except OSError:
        print(f"   [{RED}BŁĄD{RESET}] Brak wyjścia na świat!")
        return False

def check_ip():
    print(f"\n2. 🌍 SPRAWDZANIE TWOJEGO IP...")
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        ip = response.json()['ip']
        print(f"   [{GREEN}OK{RESET}] Twoje IP: {YELLOW}{ip}{RESET}")
        return True
    except Exception as e:
        print(f"   [{RED}BŁĄD{RESET}] Nie można pobrać IP: {e}")
        return False

def check_otodom_status():
    print(f"\n3. 🏠 DIAGNOSTYKA OTODOM (Test na bana)...")
    url = "https://www.otodom.pl/pl/oferty/sprzedaz/mieszkanie/wroclaw"
    
    # Stały User-Agent (zamiast losowego, który generował błędy)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pl-PL'
    }

    try:
        print(f"   Łączę się z: {url[:30]}...")
        start = time.time()
        resp = requests.get(url, headers=headers, timeout=10)
        duration = time.time() - start
        
        print(f"   Czas: {duration:.2f}s | Kod: {resp.status_code}")

        if resp.status_code == 200:
            # Szukamy śladów Captchy w treści strony
            if "Weryfikacja" in resp.text or "robot" in resp.text or "Just a moment" in resp.text:
                print(f"   [{RED}ZŁE WIEŚCI{RESET}] 🤖 Wykryto CAPTCHA / Cloudflare!")
                print("   Status: SOFT BAN (Strona działa, ale każe klikać obrazki)")
            else:
                print(f"   [{GREEN}SUKCES{RESET}] ✅ Brak blokad. Droga wolna!")
        
        elif resp.status_code == 403:
            print(f"   [{RED}ZŁE WIEŚCI{RESET}] 🚨 Błąd 403 (HARD BAN)")
            print("   Status: Twoje IP jest zablokowane przez Otodom.")
        
        elif resp.status_code == 429:
            print(f"   [{YELLOW}OSTRZEŻENIE{RESET}] ⏳ Błąd 429 (Za szybko)")
            print("   Status: Musisz odczekać 15 minut.")
            
        else:
            print(f"   [{YELLOW}INFO{RESET}] Inny kod odpowiedzi: {resp.status_code}")

    except Exception as e:
        print(f"   [{RED}BŁĄD{RESET}] Wyjątek połączenia: {e}")

def main():
    print("--- 🩺 PROSTY DOCTOR V2 ---")
    if check_internet():
        check_ip()
        check_otodom_status()
    print("\n--- KONIEC ---")

if __name__ == "__main__":
    main()