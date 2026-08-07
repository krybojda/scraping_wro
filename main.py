import csv
import os
import random
import re
import signal
import time
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from stats_readme import append_run_log

# --- KONFIGURACJA ---
FILE_NAME = os.getenv("OUTPUT_FILE", "mieszkania_wroclaw.csv")
MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", 21600))  # 6 godzin w sekundach
BASE_URL = (
    "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/dolnoslaskie/"
    "wroclaw/wroclaw/wroclaw?limit=36&ownerTypeSingleSelect=ALL&by=DEFAULT"
    "&direction=DESC&viewType=listing"
)
DISCORD_URL = os.getenv("DISCORD_URL", "")

# Definiujemy sztywna liste kolumn - to jest "bezpiecznik".
FINAL_COLUMNS = ["data_pobrania", "tytul", "cena", "metraz", "link"]

# --- LIMIT STRON ---
MAX_PAGES = int(os.getenv("MAX_PAGES", 25))

ua = UserAgent()
START_TIME = time.time()
RUN_STARTED_AT = datetime.now()

STATS = {
    "pages_scanned": 0,
    "links_found": 0,
    "offers_checked": 0,
    "saved": 0,
    "captcha": 0,
    "ban": 0,
    "http_errors": 0,
    "network_errors": 0,
    "skipped": 0,
}

stop_requested = False


def signal_handler(signum, _frame):
    global stop_requested
    print(f"\nOTRZYMANO SYGNAL ZATRZYMANIA ({signum}). Koncze bezpiecznie...")
    stop_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def interruptible_sleep(total_seconds):
    end_time = time.time() + total_seconds
    while time.time() < end_time:
        if stop_requested:
            return False
        time.sleep(min(0.5, end_time - time.time()))
    return True


def classify_status(status_key):
    if STATS["captcha"] > 0 or STATS["ban"] > 0:
        return "BLOCKED"
    if status_key == "manual_stop":
        return "MANUAL_STOP"
    if status_key == "time_limit":
        return "TIME_LIMIT"
    if status_key == "crash":
        return "CRASH"
    if status_key == "http_error":
        return "HTTP_ERROR"
    if status_key == "network_error":
        return "NETWORK_ERROR"
    if status_key == "no_listings":
        return "NO_LISTINGS"
    return "OK"


def send_discord_summary(run_status, public_ip):
    """Wysyla raport koncowy do logow i na Discorda."""
    elapsed_sec = int(time.time() - START_TIME)
    elapsed_min = elapsed_sec // 60

    print("\n" + "=" * 44)
    print("RAPORT KONCOWY (MAIN)")
    print(f"Status:               {run_status}")
    print(f"Publiczne IP:         {public_ip or 'Brak danych'}")
    print(f"Przeskanowane strony: {STATS['pages_scanned']}/{MAX_PAGES}")
    print(f"Znalezione linki:     {STATS['links_found']}")
    print(f"Sprawdzone oferty:    {STATS['offers_checked']}")
    print(f"Zapisane rekordy:     {STATS['saved']}")
    print(f"Captcha / Ban:        {STATS['captcha']} / {STATS['ban']}")
    print(f"HTTP / Network err:   {STATS['http_errors']} / {STATS['network_errors']}")
    print(f"Pominiete oferty:     {STATS['skipped']}")
    print(f"Czas pracy:           {elapsed_min} min ({elapsed_sec}s)")
    print(f"Plik wyjsciowy:       {FILE_NAME}")
    print("=" * 44 + "\n")

    if not DISCORD_URL or "TWOJ_ID" in DISCORD_URL:
        return

    ping_msg = ""
    if run_status in ("BLOCKED", "CRASH", "HTTP_ERROR", "NETWORK_ERROR"):
        color = 15548997
        title = f"RPi Zwiadowca: {run_status}"
        ping_msg = "@everyone Wymagana interwencja."
    elif run_status == "MANUAL_STOP":
        color = 16776960
        title = "RPi Zwiadowca: Zatrzymano recznie"
    elif run_status == "TIME_LIMIT":
        color = 16776960
        title = "RPi Zwiadowca: Koniec czasu"
    elif STATS["saved"] > 0:
        color = 5814783
        title = "RPi Zwiadowca: Sukces"
        ping_msg = "@here Zapisano nowe rekordy."
    else:
        color = 12370112
        title = "RPi Zwiadowca: Brak nowosci"

    embed = {
        "title": title,
        "color": color,
        "fields": [
            {"name": "Status", "value": run_status, "inline": True},
            {"name": "Publiczne IP", "value": public_ip or "Brak danych", "inline": True},
            {"name": "Plik", "value": FILE_NAME, "inline": False},
            {"name": "Strony", "value": f"{STATS['pages_scanned']}/{MAX_PAGES}", "inline": True},
            {"name": "Linki", "value": str(STATS["links_found"]), "inline": True},
            {"name": "Sprawdzone", "value": str(STATS["offers_checked"]), "inline": True},
            {"name": "Zapisane", "value": str(STATS["saved"]), "inline": True},
            {"name": "Captcha/Ban", "value": f"{STATS['captcha']} / {STATS['ban']}", "inline": True},
            {
                "name": "HTTP/Network errors",
                "value": f"{STATS['http_errors']} / {STATS['network_errors']}",
                "inline": True,
            },
            {"name": "Pominiete", "value": str(STATS["skipped"]), "inline": True},
            {"name": "Czas pracy", "value": f"{elapsed_min} min ({elapsed_sec}s)", "inline": True},
        ],
        "footer": {"text": f"Start: {RUN_STARTED_AT.strftime('%Y-%m-%d %H:%M')}"},
    }
    payload = {"content": ping_msg, "embeds": [embed]}
    try:
        requests.post(DISCORD_URL, json=payload, timeout=10)
    except Exception as exc:
        print(f"Discord webhook error: {exc}")


def get_public_ip():
    """Zwraca publiczne IP lub pusty string, gdy nie da sie pobrac."""
    try:
        resp = requests.get("https://api.ipify.org", timeout=5)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception:
        pass
    return ""


def make_request(url):
    """Pobieranie z rotacja User-Agent. Zwraca (soup, status)."""
    if stop_requested:
        return None, "MANUAL_STOP"

    try:
        headers = {
            "User-Agent": ua.random,
            "Accept-Language": "pl-PL",
        }
        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code in [403, 429]:
            print(f"!!! BAN IP ({response.status_code}) !!!")
            return None, "BAN"
        if response.status_code != 200:
            print(f"HTTP {response.status_code} dla: {url}")
            return None, "HTTP_ERROR"

        soup = BeautifulSoup(response.content, "html.parser")
        if soup.title and "captcha" in soup.title.text.lower():
            print("!!! SOFT BAN (Captcha) !!!")
            return None, "CAPTCHA"

        return soup, "OK"
    except Exception as exc:
        print(f"Blad sieci: {exc}")
        return None, "ERROR"


def get_listing_basic(url):
    """Szybkie pobieranie podstawowych danych (HTML)."""
    try:
        # Losowe opoznienie, zeby udawac czlowieka.
        if not interruptible_sleep(random.uniform(2, 5)):
            return None, "MANUAL_STOP"

        soup, status = make_request(url)
        if status != "OK":
            return None, status

        title = soup.find("h1", {"data-cy": "adPageAdTitle"})
        title = title.text.strip() if title else "Brak tytulu"

        price = soup.find("strong", {"data-cy": "adPageHeaderPrice"})
        if price:
            price = re.sub(r"[^\d,.]", "", price.text).strip()
            if not price:
                price = "0"
        else:
            price = "0"

        area = "0"
        # Szukanie metrazu w tekscie (proste, ale moze byc niedokladne).
        found = re.search(r"(\d+[.,]?\d*)\s*m(?:2|²)?", soup.text, re.IGNORECASE)
        if found:
            area = found.group(1).replace(",", ".").strip()

        return {
            "data_pobrania": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tytul": title,
            "cena": price,
            "metraz": area,
            "link": url,
        }, "OK"
    except Exception as exc:
        print(f"Blad parsowania oferty: {exc}")
        return None, "PARSE_ERROR"


def main():
    print(f"--- START ZWIADOWCY --- Plik: {FILE_NAME}")
    print(f"Limit stron: {MAX_PAGES}")

    ip = get_public_ip()
    print(f"Aktualne IP: {ip if ip else 'Brak danych'}")

    page = 1
    run_status_key = "ok"

    try:
        # GLOWNA PETLA Z LIMITEM STRON
        while page <= MAX_PAGES:
            if stop_requested:
                run_status_key = "manual_stop"
                break

            if (time.time() - START_TIME) > MAX_EXECUTION_TIME:
                print("Koniec czasu.")
                run_status_key = "time_limit"
                break

            print(f"Skanuje strone {page}/{MAX_PAGES}...")
            soup, status = make_request(f"{BASE_URL}&page={page}")
            if status == "MANUAL_STOP":
                run_status_key = "manual_stop"
                break
            if status == "BAN":
                STATS["ban"] += 1
                break
            if status == "CAPTCHA":
                STATS["captcha"] += 1
                break
            if status == "HTTP_ERROR":
                STATS["http_errors"] += 1
                run_status_key = "http_error"
                break
            if status == "ERROR":
                STATS["network_errors"] += 1
                run_status_key = "network_error"
                break

            STATS["pages_scanned"] += 1

            articles = soup.find_all("a", {"data-cy": "listing-item-link"})
            if not articles:
                run_status_key = "no_listings"
                break

            links = ["https://www.otodom.pl" + a["href"] for a in articles]
            STATS["links_found"] += len(links)

            page_data = []
            blocked = False
            for link in links:
                if stop_requested:
                    run_status_key = "manual_stop"
                    blocked = True
                    break

                if (time.time() - START_TIME) > MAX_EXECUTION_TIME:
                    run_status_key = "time_limit"
                    blocked = True
                    break

                STATS["offers_checked"] += 1
                print(f" -> {link[-20:]}")
                details, offer_status = get_listing_basic(link)

                if offer_status == "OK" and details:
                    page_data.append(details)
                    continue

                if offer_status == "MANUAL_STOP":
                    run_status_key = "manual_stop"
                    blocked = True
                    break
                if offer_status == "BAN":
                    STATS["ban"] += 1
                    blocked = True
                    break
                if offer_status == "CAPTCHA":
                    STATS["captcha"] += 1
                    blocked = True
                    break
                if offer_status == "HTTP_ERROR":
                    STATS["http_errors"] += 1
                elif offer_status == "ERROR":
                    STATS["network_errors"] += 1

                STATS["skipped"] += 1

            if blocked:
                break

            if page_data:
                df = pd.DataFrame(page_data)

                # --- SEKCJA BEZPIECZENSTWA ---
                # 1. Upewniamy sie, ze mamy kolumne "metraz".
                if "metraz" not in df.columns:
                    df["metraz"] = ""

                # 2. Dodajemy brakujace kolumny.
                for col in FINAL_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""

                # 3. WYMUSZAMY KOLEJNOSC KOLUMN.
                df = df[FINAL_COLUMNS]
                # -----------------------------

                exists = os.path.isfile(FILE_NAME)
                df.to_csv(
                    FILE_NAME,
                    mode="a",
                    header=not exists,
                    index=False,
                    quoting=csv.QUOTE_MINIMAL,
                    escapechar="\\",
                )
                STATS["saved"] += len(page_data)
                print(f"Zapisano {len(page_data)} rekordow.")

            page += 1
            # Przerwa miedzy stronami listingu.
            if not interruptible_sleep(random.uniform(5, 30)):
                run_status_key = "manual_stop"
                break
    except KeyboardInterrupt:
        run_status_key = "manual_stop"
        print("Przerwano recznie (KeyboardInterrupt).")
    except Exception as exc:
        run_status_key = "crash"
        print(f"KRYTYCZNY BLAD PETLI: {exc}")
    finally:
        run_status = classify_status(run_status_key)
        send_discord_summary(run_status, ip)
        try:
            append_run_log(
                component="scraper",
                found=STATS["links_found"],
                saved=STATS["saved"],
                output_file=FILE_NAME,
                status=run_status,
            )
        except Exception as exc:
            print(f"Stats README write error: {exc}")


if __name__ == "__main__":
    main()
