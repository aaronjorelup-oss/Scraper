@echo off
title AERI Parts Scraper - Running
echo ======================================
echo  AERI Parts Scraper
echo  Started: %date% %time%
echo  Do not close this window.
echo ======================================
echo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python main_scraper.py >> scraper_log.txt 2>&1
echo.
echo Scraper finished. This window will close in 10 seconds.
timeout /t 10