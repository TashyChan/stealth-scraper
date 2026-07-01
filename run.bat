@echo off
title Stealth Scraper
color 0A

echo.
echo =============================================
echo           STEALTH SCRAPER
echo =============================================
echo.
echo Starting server... Chrome will open in a few seconds.
echo To stop the app, close this window.
echo.

:: Check if streamlit is available
python -m streamlit --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Streamlit not found. Please run install.bat first!
    pause
    exit /b 1
)

:: Open Chrome after a 4-second delay (gives server time to start)
set URL=http://localhost:8501
set CHROME1="C:\Program Files\Google\Chrome\Application\chrome.exe"
set CHROME2="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

if exist %CHROME1% (
    start "" cmd /c "timeout /t 4 /nobreak >nul && start "" %CHROME1% %URL%"
) else if exist %CHROME2% (
    start "" cmd /c "timeout /t 4 /nobreak >nul && start "" %CHROME2% %URL%"
) else (
    start "" cmd /c "timeout /t 4 /nobreak >nul && powershell -command Start-Process chrome '%URL%'"
)

:: Run Streamlit in foreground (headless config stops it opening its own browser)
python -m streamlit run app.py

pause
