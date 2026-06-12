@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python main_scraper.py >> output\scraper_log.txt 2>&1