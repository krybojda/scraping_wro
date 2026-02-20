import os

plik_readme = 'readme.md'

# === 1. OBSŁUGA SCRAPERA (Wkleja w środek pliku) ===
if os.path.exists('temp_scraper.txt'):
    with open('temp_scraper.txt', 'r') as f:
        nowy_wpis = f.read().strip() + '\n'
        
    with open(plik_readme, 'r') as f:
        linie = f.readlines()
        
    for i, linia in enumerate(linie):
        if '## Processor run history' in linia:
            # Wklej nową linijkę ciut wyżej (nad drugą tabelą)
            linie.insert(i-1, nowy_wpis)
            break
            
    with open(plik_readme, 'w') as f:
        f.writelines(linie)
        
    print("✅ Dodano statystyki Zwiadowcy (Scrapera) do Readme.")

# === 2. OBSŁUGA PROCESSORA (Wkleja na sam dół) ===
if os.path.exists('temp_processor.txt'):
    with open('temp_processor.txt', 'r') as f:
        nowy_wpis = f.read().strip() + '\n'
        
    # Skoro tabela Processora jest na końcu pliku, dopisujemy po prostu na sam dół ('a' - append)
    with open(plik_readme, 'a') as f:
        f.write(nowy_wpis)
        

    print("✅ Dodano statystyki Processora do Readme.")