# Przeglądarka mieszkań z CSV — scraping Wrocław

To jest prosta aplikacja webowa w **Streamlit**, która pozwala:

- przeglądać rekordy mieszkań z pliku `.csv`
- filtrować po liczbach, datach, kategoriach i tekście
- sortować po dowolnej kolumnie
- ukrywać/pokazywać kolumny
- pobierać przefiltrowane wyniki do nowego CSV

## 1. Instalacja

### Windows / PowerShell
```powershell
cd .\scraping_wroclaw_csv_browser
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

### Linux
```bash
cd scraping_wroclaw_csv_browser
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## 2. Uruchomienie z domyślnym plikiem CSV

Możesz ustawić ścieżkę do pliku przez zmienną środowiskową `CSV_PATH`.

### Windows / PowerShell
```powershell
$env:CSV_PATH = "C:\\sciezka\\do\\mieszkania.csv"
py -m streamlit run app.py
```

### Linux
```bash
export CSV_PATH="/ścieżka/do/mieszkania.csv"
streamlit run app.py
```

## 3. Jak używać

Po uruchomieniu:

1. wgraj plik CSV **albo** wpisz jego ścieżkę,
2. użyj filtrów z lewego panelu,
3. wybierz kolumnę sortowania i kierunek,
4. pobierz przefiltrowane dane przyciskiem na dole.

## 4. Dlaczego to rozwiązanie jest dobre

Bo jest:

- szybkie do wdrożenia,
- wygodne w użyciu przez przeglądarkę,
- łatwe do późniejszej rozbudowy,
- dobre zarówno lokalnie, jak i na VPS.

## 5. Co można dodać później

W kolejnym kroku można dorobić:

- zapisywanie własnych presetów filtrów,
- wykres cen i metrażu,
- deduplikację rekordów,
- porównywanie nowych ofert z poprzednim CSV,
- panel „tylko nowe / tylko tanie / tylko z balkonem / tylko z garażem”.
