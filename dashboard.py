import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Mieszkania Wrocław", layout="wide")
st.title("🏡 Centrum Dowodzenia: Wrocław")

FILE = "mieszkania_complete.csv"

if not os.path.exists(FILE):
    st.error("Brak pliku z danymi. Uruchom procesor!")
else:
    df = pd.read_csv(FILE)
    
    # Czyszczenie ceny do liczb
    df['cena_num'] = pd.to_numeric(df['cena'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
    
    # Pasek boczny (Filtry)
    st.sidebar.header("Filtry")
    max_price = st.sidebar.slider("Maksymalna Cena", 1000, 10000, 4000)
    min_area = st.sidebar.slider("Minimalny Metraż", 10, 100, 30)

    # Filtrowanie
    mask = (df['cena_num'] <= max_price)
    # Tu można dodać filtr metrażu jeśli kolumna jest liczbowa
    
    df_filtered = df[mask]

    # Statystyki
    col1, col2, col3 = st.columns(3)
    col1.metric("Znalezionych ofert", len(df_filtered))
    col2.metric("Średnia cena", f"{df_filtered['cena_num'].mean():.0f} zł")
    col3.metric("Najtańsze", f"{df_filtered['cena_num'].min():.0f} zł")

    # Wykres
    st.bar_chart(df_filtered['cena_num'])

    # Tabela
    st.dataframe(df_filtered[['data_pobrania', 'tytul', 'cena', 'czynsz', 'pietro', 'lokalizacja', 'link']])