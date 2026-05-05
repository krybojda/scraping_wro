from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass
from typing import BinaryIO, Iterable

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Przeglądarka mieszkań CSV", layout="wide")

DATE_KEYWORDS = ["data", "date", "czas", "time", "dodano", "updated", "utworzono", "published"]
PRICE_KEYWORDS = ["cena", "price", "kwota"]
AREA_KEYWORDS = ["metraz", "metraż", "powierzchnia", "m2", "m²", "area"]
ROOM_KEYWORDS = ["pokoj", "pokój", "rooms", "liczba_pokoi"]
DISTRICT_KEYWORDS = ["dzielnica", "osiedle", "lokalizacja", "rejon", "district"]
ID_LIKE_KEYWORDS = ["id", "link", "url", "telefon", "phone", "kontakt"]


@dataclass
class CsvSource:
    text: str
    name: str


def try_decode(raw: bytes) -> str:
    encodings = ["utf-8-sig", "utf-8", "cp1250", "latin1"]
    for enc in encodings:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in [";", ",", "\t", "|"]}
        return max(counts, key=counts.get)


def get_source(uploaded_file, path: str) -> CsvSource | None:
    if uploaded_file is not None:
        raw = uploaded_file.getvalue()
        return CsvSource(text=try_decode(raw), name=uploaded_file.name)

    path = path.strip()
    if not path:
        return None
    if not os.path.exists(path):
        raise FileNotFoundError(f"Nie znaleziono pliku: {path}")
    with open(path, "rb") as f:
        raw = f.read()
    return CsvSource(text=try_decode(raw), name=os.path.basename(path))


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = []
    seen: dict[str, int] = {}
    for col in df.columns:
        new_col = str(col).strip().replace("\n", " ")
        if new_col in seen:
            seen[new_col] += 1
            new_col = f"{new_col}_{seen[new_col]}"
        else:
            seen[new_col] = 0
        cols.append(new_col)
    df.columns = cols
    return df


def clean_numeric_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("\xa0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("zł", "", regex=False)
        .str.replace("pln", "", case=False, regex=True)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^0-9.\-]", "", regex=True)
        .replace({"": None, "-": None, ".": None, "nan": None, "None": None})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def maybe_parse_numeric(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    converted: list[str] = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_datetime64_any_dtype(df[col]):
            continue

        lower_col = col.lower()
        if any(k in lower_col for k in ID_LIKE_KEYWORDS):
            continue

        non_empty = df[col].dropna().astype(str).str.strip()
        if non_empty.empty:
            continue

        numeric = clean_numeric_series(df[col])
        ratio = numeric.notna().sum() / max(len(non_empty), 1)

        if ratio >= 0.80:
            df[col] = numeric
            converted.append(col)
    return df, converted


def maybe_parse_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    converted: list[str] = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        lower_col = col.lower()
        if not any(k in lower_col for k in DATE_KEYWORDS):
            continue
        parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        ratio = parsed.notna().sum() / max(df[col].notna().sum(), 1)
        if ratio >= 0.60:
            df[col] = parsed
            converted.append(col)
    return df, converted


@st.cache_data(show_spinner=False)
def load_dataframe(text: str) -> tuple[pd.DataFrame, dict]:
    delimiter = sniff_delimiter(text[:5000])
    df = pd.read_csv(io.StringIO(text), sep=delimiter)
    df = normalize_columns(df)
    df, date_cols = maybe_parse_dates(df)
    df, numeric_cols = maybe_parse_numeric(df)

    info = {
        "delimiter": delimiter,
        "date_cols": date_cols,
        "numeric_cols": numeric_cols,
        "rows": len(df),
        "cols": len(df.columns),
    }
    return df, info


def keyword_match(columns: Iterable[str], keywords: list[str]) -> str | None:
    for col in columns:
        low = col.lower()
        if any(k in low for k in keywords):
            return col
    return None


def format_metric(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (int, float)):
        if abs(value) >= 1000:
            return f"{value:,.0f}".replace(",", " ")
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def render_full_width_table(df: pd.DataFrame) -> None:
    display_df = df.copy()

    for col in display_df.columns:
        if pd.api.types.is_datetime64_any_dtype(display_df[col]):
            display_df[col] = display_df[col].dt.strftime("%Y-%m-%d %H:%M").fillna("")
        elif pd.api.types.is_float_dtype(display_df[col]):
            display_df[col] = display_df[col].map(lambda x: "" if pd.isna(x) else f"{x:.2f}".rstrip("0").rstrip("."))
        elif pd.api.types.is_integer_dtype(display_df[col]):
            display_df[col] = display_df[col].map(lambda x: "" if pd.isna(x) else str(int(x)))
        else:
            display_df[col] = display_df[col].where(display_df[col].notna(), "")

    html = display_df.to_html(index=False, escape=False, render_links=True)

    st.markdown(
        """
        <style>
        .full-width-table-wrap {
            width: 100%;
            overflow-x: auto;
            overflow-y: visible;
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 10px;
            background: transparent;
        }
        .full-width-table-wrap table {
            width: max-content;
            min-width: 100%;
            border-collapse: collapse;
            font-size: 0.92rem;
        }
        .full-width-table-wrap thead th {
            position: sticky;
            top: 0;
            background: #eef2f7;
            color: #111827;
            z-index: 2;
            text-align: left;
            box-shadow: inset 0 -1px 0 rgba(128, 128, 128, 0.28);
        }
        .full-width-table-wrap th,
        .full-width-table-wrap td {
            padding: 0.55rem 0.7rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.18);
            vertical-align: top;
            white-space: nowrap;
            word-break: normal;
        }
        .full-width-table-wrap tbody tr:hover {
            background: rgba(128, 128, 128, 0.08);
        }
        .full-width-table-wrap a {
            color: inherit;
            text-decoration: underline;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="full-width-table-wrap">{html}</div>', unsafe_allow_html=True)


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    filtered = df.copy()

    st.sidebar.header("Filtry")

    search_text = st.sidebar.text_input("Szukaj we wszystkich kolumnach", placeholder="np. Krzyki, balkon, garaż")
    if search_text:
        mask = pd.Series(False, index=filtered.index)
        for col in filtered.columns:
            mask = mask | filtered[col].astype(str).str.contains(search_text, case=False, na=False)
        filtered = filtered[mask]

    numeric_cols = [c for c in filtered.columns if pd.api.types.is_numeric_dtype(filtered[c])]
    datetime_cols = [c for c in filtered.columns if pd.api.types.is_datetime64_any_dtype(filtered[c])]
    object_cols = [c for c in filtered.columns if c not in numeric_cols and c not in datetime_cols]

    with st.sidebar.expander("Filtry liczbowe", expanded=True):
        for col in numeric_cols:
            non_na = filtered[col].dropna()
            if non_na.empty:
                continue
            min_val = float(non_na.min())
            max_val = float(non_na.max())
            if min_val == max_val:
                continue
            label = f"{col}"
            start, end = st.slider(label, min_value=min_val, max_value=max_val, value=(min_val, max_val))
            filtered = filtered[filtered[col].fillna(min_val).between(start, end)]

    with st.sidebar.expander("Filtry dat", expanded=False):
        for col in datetime_cols:
            non_na = filtered[col].dropna()
            if non_na.empty:
                continue
            min_date = non_na.min().date()
            max_date = non_na.max().date()
            start_date, end_date = st.date_input(
                f"{col}",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )
            if isinstance(start_date, tuple) or isinstance(start_date, list):
                # zabezpieczenie na różne zwroty widgetu
                start_date, end_date = start_date
            filtered = filtered[
                filtered[col].dt.date.between(start_date, end_date)
                | filtered[col].isna()
            ]

    category_candidates = []
    for col in object_cols:
        nunique = filtered[col].nunique(dropna=True)
        if 1 < nunique <= 25:
            category_candidates.append(col)

    with st.sidebar.expander("Filtry kategorii", expanded=True):
        for col in category_candidates:
            options = sorted([str(x) for x in filtered[col].dropna().unique()])
            selected = st.multiselect(col, options, default=options)
            if len(selected) != len(options):
                filtered = filtered[filtered[col].astype(str).isin(selected)]

    with st.sidebar.expander("Kolumny tekstowe — zawiera", expanded=False):
        chosen_text_cols = st.multiselect(
            "Wybierz kolumny do filtrowania tekstowego",
            options=object_cols,
            default=[],
        )
        for col in chosen_text_cols:
            phrase = st.text_input(f"{col}")
            if phrase:
                filtered = filtered[filtered[col].astype(str).str.contains(phrase, case=False, na=False)]

    return filtered


def render_metrics(df: pd.DataFrame) -> None:
    price_col = keyword_match(df.columns, PRICE_KEYWORDS)
    area_col = keyword_match(df.columns, AREA_KEYWORDS)
    rooms_col = keyword_match(df.columns, ROOM_KEYWORDS)
    district_col = keyword_match(df.columns, DISTRICT_KEYWORDS)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Liczba rekordów", format_metric(len(df)))

    if price_col and pd.api.types.is_numeric_dtype(df[price_col]):
        c2.metric("Mediana ceny", format_metric(df[price_col].median()))
    else:
        c2.metric("Mediana ceny", "—")

    if area_col and pd.api.types.is_numeric_dtype(df[area_col]):
        c3.metric("Mediana metrażu", format_metric(df[area_col].median()))
    else:
        c3.metric("Mediana metrażu", "—")

    if rooms_col and pd.api.types.is_numeric_dtype(df[rooms_col]):
        c4.metric("Śr. liczba pokoi", format_metric(df[rooms_col].mean()))
    elif district_col:
        dominant = df[district_col].mode(dropna=True)
        c4.metric("Najczęstsza lokalizacja", str(dominant.iloc[0]) if not dominant.empty else "—")
    else:
        c4.metric("Najczęstsza lokalizacja", "—")


def main() -> None:
    st.title("Przeglądarka rekordów mieszkań z CSV")
    st.caption("Filtrowanie, sortowanie, wyszukiwanie i eksport wyników z projektu scraping Wrocław.")

    default_path = os.environ.get("CSV_PATH", "")

    with st.sidebar:
        st.header("Źródło danych")
        uploaded_file = st.file_uploader("Wczytaj plik CSV", type=["csv"])
        path = st.text_input("albo podaj ścieżkę do pliku na dysku / serwerze", value=default_path)

    try:
        source = get_source(uploaded_file, path)
    except Exception as e:
        st.error(str(e))
        st.stop()

    if source is None:
        st.info("Wgraj plik CSV albo wpisz ścieżkę do pliku, aby rozpocząć.")
        st.stop()

    try:
        df, info = load_dataframe(source.text)
    except Exception as e:
        st.error(f"Nie udało się wczytać CSV: {e}")
        st.stop()

    with st.expander("Informacje o pliku", expanded=False):
        st.write(
            {
                "plik": source.name,
                "separator": info["delimiter"],
                "liczba_wierszy": info["rows"],
                "liczba_kolumn": info["cols"],
                "wykryte_kolumny_dat": info["date_cols"],
                "wykryte_kolumny_liczbowe": info["numeric_cols"],
            }
        )

    filtered = apply_filters(df)

    st.subheader("Podsumowanie")
    render_metrics(filtered)

    st.subheader("Widok tabeli")
    c1, c2, c3 = st.columns([2, 1, 1])
    visible_columns = c1.multiselect("Widoczne kolumny", list(filtered.columns), default=list(filtered.columns))
    sort_col = c2.selectbox("Sortuj po", options=list(filtered.columns))
    sort_order = c3.selectbox("Kierunek", options=["Rosnąco", "Malejąco"])

    table = filtered[visible_columns].copy() if visible_columns else filtered.copy()

    ascending = sort_order == "Rosnąco"
    try:
        table = table.sort_values(by=sort_col, ascending=ascending, na_position="last")
    except Exception:
        pass

    page_size = st.selectbox("Liczba wierszy na widoku", options=[25, 50, 100, 250, 500], index=1)
    page_count = max((len(table) - 1) // page_size + 1, 1)
    page = st.number_input("Strona", min_value=1, max_value=page_count, value=1, step=1)

    start = (page - 1) * page_size
    end = start + page_size

    st.caption(f"Pokazuję rekordy {start + 1}–{min(end, len(table))} z {len(table)}")
    render_full_width_table(table.iloc[start:end])

    csv_out = table.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Pobierz przefiltrowany widok do CSV",
        data=csv_out,
        file_name="mieszkania_filtrowane.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
