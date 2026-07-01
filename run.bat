@echo off
title Stealth Scraper
color 0A

echo.
echo =============================================
echo           STEALTH SCRAPER
echo =============================================
echo.
echo Starting... please wait.
echo.

python -m streamlit --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Streamlit not found. Please run install.bat first!
    pause
    exit /b 1
)

python -m streamlit run app.py --server.headless false --browser.gatherUsageStats false

pause
