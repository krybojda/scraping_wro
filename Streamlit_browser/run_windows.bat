@echo off
setlocal

if "%CSV_PATH%"=="" (
    echo [INFO] CSV_PATH nie jest ustawiony. Aplikacja uruchomi sie bez domyslnej sciezki.
) else (
    echo [INFO] CSV_PATH=%CSV_PATH%
)

streamlit run app.py
