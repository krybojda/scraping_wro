#!/bin/bash
# shellcheck disable=SC2129

# --- KONFIGURACJA ---
CDir="$(cd "$(dirname "$0")" && pwd)"
# Upewniamy się, że nazwa logu jest poprawna
LOGfile="$CDir/logs/log_$(date +'%Y-%m-%d').txt"

# Tworzymy katalog, jeśli nie istnieje
mkdir -p "$CDir/logs"

# Bezpieczne wejście do katalogu - jeśli pendrive nie jest zamontowany, skrypt kończy (żeby nie śmiecić w systemie)
cd "$CDir" || { echo "❌ BŁĄD: Nie znaleziono katalogu $CDir (Pendrive odłączony?)" >> "/var/log/syslog"; exit 1; }

echo "=== START: $(date) ===" >> "$LOGfile"

# 0. BEZPIECZEŃSTWO: Usuń ewentualne blokady Gita po awarii prądu
rm -f .git/index.lock

# 1. DIAGNOSTYKA IP (Zapisujemy, żebyś widział w logach czy RPi miało neta)
PUBLIC_IP="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || echo "BRAK_SIECI")"
echo "Public IP: $PUBLIC_IP" >> "$LOGfile"

# 2. AKTUALIZACJA PRZED PRACĄ (Ważne!)
# Jeśli to się nie uda (brak neta), to trudno - idziemy dalej, może Python ruszy.
echo "📥 [GIT] Pobieranie zmian..." >> "$LOGfile"
git pull --rebase origin main >> "$LOGfile" 2>&1

# 3. URUCHOMIENIE BOTA
# timeout 6h zabezpiecza przed zawieszeniem. "-u" wyłącza buforowanie (logi spływają na bieżąco).
echo "🤖 [PYTHON] Start processora..." >> "$LOGfile"
timeout 6h python3 -u processor.py >> "$LOGfile" 2>&1 || true

echo "--- Python zakończył pracę. Rozpoczynam synchronizację... ---" >> "$LOGfile"

# 4. ZATWIERDZANIE ZMIAN
# WAŻNE: Dodajemy tylko pliki CSV (bazy danych), żeby nie wysyłać logów do GitHuba!
git add ./*.csv >> "$LOGfile" 2>&1

# Sprawdzamy, czy w ogóle mamy coś do wysłania (status gita)
# Jeśli nie ma zmian w plikach śledzonych, git diff --quiet zwróci 0 (prawda)
if git diff --quiet && git diff --staged --quiet; then
    echo "Brak zmian w danych. Nie wysyłam."
    exit 0
fi

# 5. SYNCHRONIZACJA KOŃCOWA (To łączy pracę Node 1 i Node 2)
# Jeśli działamy w CI (tryb testowy), to nie wysyłamy zmian, ale w normalnym trybie (TRYB_MASTER=true) wysyłamy.
if [ -z "${CI:-}" ] || [ "${TRYB_MASTER:-}" = "true" ]; then

  echo "Wykryto zmiany i tryb zapisu. Commituję..." >> "$LOGfile"

  # ZATWIERDZANIE ZMIAN (Commit)
  git commit -m "Auto-zapis Node $(hostname): $(date +'%Y-%m-%d %H:%M')" >> "$LOGfile" 2>&1
  
  # 5. SYNCHRONIZACJA KOŃCOWA (To łączy pracę Node 1 i Node 2)
  echo "🔄 [GIT] Pobieranie i łączenie zmian (Rebase)..." >> "$LOGfile"
  git pull --rebase origin main >> "$LOGfile" 2>&1
  
  # 6. WYSŁANIE DO CHMURY
  echo "📤 [GIT] Wysyłanie do chmury..." >> "$LOGfile"
  git push origin main >> "$LOGfile" 2>&1

  echo "Sukces! Dane wysłane na GitHub."

else
    echo "Tryb testowy (CI bez uprawnień). Zmiany nie zostały wysłane."
fi


echo "=== KONIEC: $(date) ===" >> "$LOGfile"
# Pusta linia dla czytelności w logu
echo "" >> "$LOGfile"
