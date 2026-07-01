@echo off
title Stealth Scraper
color 0A

echo.
echo =============================================
echo           STEALTH SCRAPER
echo =============================================
echo.
echo Starting the app...
echo Your browser will open automatically.
echo.
echo To stop the app, close this window.
echo.

:: Check if streamlit is available
python -m streamlit --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Streamlit not found.
    echo Please run install.bat first!
    echo.
    pause
    exit /b 1
)

:: Launch the app (suppress auto-open, then open Chrome manually)
start "" "chrome.exe" "http://localhost:8501"
python -m streamlit run app.py --server.headless false --browser.serverAddress localhost --server.port 8501

if %errorlevel% neq 0 (
    echo.
    echo Something went wrong launching the app.
    echo Make sure you ran install.bat first.
    echo.
    pause
)
