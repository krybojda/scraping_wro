import requests
import time
import socket
from fake_useragent import UserAgent

# Kolory dla czytelności
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_internet():
    print(f"\n1. 🌐 SPRAWDZANIE POŁĄCZENIA Z SIECIĄ...")
    try:
        # Próba połączenia z DNS Google (szybki test ping)
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        print(f"   [{GREEN}OK{RESET}] Internet działa.")
        return True
    except OSError:
        print(f"   [{RED}BŁĄD{RESET}] Brak dostępu do Internetu!")
        return False

def check_ip():
    print(f"\n2. 🌍 SPRAWDZANIE PUBLICZNEGO IP...")
    try:
        ip = requests.get('https://api.ipify.org', timeout=5).text
        print(f"   [{GREEN}OK{RESET}] Twoje IP: {YELLOW}{ip}{RESET}")
        return True
    except Exception as e:
        print(f"   [{RED}BŁĄD{RESET}] Nie można pobrać IP. ({e})")
        return False

def check_otodom_status():
    print(f"\n3. 🏠 DIAGNOSTYKA OTODOM (Test Bana/Captchy)...")
    url = "https://www.otodom.pl/pl/oferty/sprzedaz/mieszkanie/wroclaw"
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }

    try:
        print(f"   Wysyłam zapytanie jako: {headers['User-Agent'][:30]}...")
        start = time.time()
        resp = requests.get(url, headers=headers, timeout=10)
        duration = time.time() - start
        
        print(f"   Czas odpowiedzi: {duration:.2f}s")
        print(f"   Kod statusu: {resp.status_code}")

        # --- ANALIZA WYNIKU ---
        if resp.status_code == 200:
            # Sprawdzamy czy nie ma ukrytej Captchy w treści 200 OK
            if "Weryfikacja" in resp.text or "robot" in resp.text or "Just a moment" in resp.text:
                print(f"   [{RED}CRITICAL{RESET}] 🤖 WYKRYTO CAPTCHA / CLOUDFLARE!")
                print("   Status: SOFT BAN (Wymagana interwencja w przeglądarce lub zmiana IP)")
            else:
                print(f"   [{GREEN}SUKCES{RESET}] ✅ Brak blokad. Można scrapować.")
        
        elif resp.status_code == 403:
            print(f"   [{RED}CRITICAL{RESET}] 🚨 403 FORBIDDEN (HARD BAN)")
            print("   Status: Twoje IP jest na czarnej liście. Zmień IP!")
        
        elif resp.status_code == 429:
            print(f"   [{YELLOW}OSTRZEŻENIE{RESET}] ⏳ 429 TOO MANY REQUESTS")
            print("   Status: Za szybko. Odczekaj 15 minut.")
            
        else:
            print(f"   [{YELLOW}INFO{RESET}] Inny kod błędu: {resp.status_code}")

    except Exception as e:
        print(f"   [{RED}BŁĄD{RESET}] Nie udało się połączyć z Otodom: {e}")
        if "ConnectTimeout" in str(e):
            print("   (Możliwy firewall/blokada sieciowa)")

def main():
    print("--- 🩺 OTODOM DOCTOR (Diagnostyka) ---")
    if check_internet():
        check_ip()
        check_otodom_status()
    print("\n--- KONIEC DIAGNOSTYKI ---")

if __name__ == "__main__":
    main()