@echo off
title Stealth Scraper - Installer
color 0A

echo.
echo =============================================
echo         STEALTH SCRAPER - INSTALLER
echo =============================================
echo.
echo This will install everything you need.
echo Please do NOT close this window.
echo.
pause

:: ── Check Python ──────────────────────────────────────────
echo.
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python first:
    echo   1. Go to https://python.org/downloads
    echo   2. Download and run the installer
    echo   3. CHECK the box that says "Add Python to PATH"
    echo   4. Run this installer again
    echo.
    pause
    exit /b 1
)
python --version
echo Python found!

:: ── Install pip packages ───────────────────────────────────
echo.
echo [2/4] Installing required packages...
echo (This may take a few minutes)
echo.
python -m pip install --upgrade pip --quiet
python -m pip install streamlit curl-cffi beautifulsoup4 fake-useragent lxml playwright google-api-python-client --quiet
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install packages.
    echo Please check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo Packages installed!

:: ── Install Playwright browsers ────────────────────────────
echo.
echo [3/4] Installing browser for advanced scraping...
echo (This downloads ~150MB - please wait)
echo.
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Browser installation failed.
    echo Basic scraping will still work, but Twitter,
    echo LinkedIn, Amazon and G2 tabs may not work.
    echo.
)
echo Browser installed!

:: ── Done ──────────────────────────────────────────────────
echo.
echo =============================================
echo         INSTALLATION COMPLETE!
echo =============================================
echo.
echo You can now close this window and
echo double-click RUN.bat to start the app.
echo.
pause
