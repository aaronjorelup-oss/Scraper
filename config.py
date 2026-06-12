"""
config.py - Centralized configuration
======================================
All credentials, settings, and the canonical CSV field list live here.
NEVER commit this file to a public repo (or share it).
"""

import os

# Folder where the scraper CSVs will be saved.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = "F:\\Purchasing\\AaronO\\Webscraper\\output"

# Whether to show the browser while scraping.
# True  = visible browser (good for debugging)
# False = headless (faster, runs in background, use for cron jobs)
SHOW_BROWSER = False

# How many seconds to wait between part searches (be polite to the sites)
DELAY_BETWEEN_SEARCHES = 1

# =============================================================
# SCHEDULING / BATCHING
# =============================================================

# How many parts to scrape before each pause.
PARTS_PER_BATCH = 10

# Minutes to wait between batches (keeps the load light on the supplier sites).
BATCH_PAUSE_MINUTES = 30

# Operating hours (24-hour clock). A new batch only starts inside this window.
# A batch already in progress is allowed to finish past the end time.
BUSINESS_HOURS_START = 3     # don't start before 6:00 AM
BUSINESS_HOURS_END   = 17    # don't start a new batch at/after 5:00 PM

# Safety ceiling on how many parts a single cycle will ever process.
# Protects against a runaway database result. None = no cap.
MAX_PARTS_PER_CYCLE = None   # e.g. set to 300 once you know your typical volume

# Progress file — lets the scraper resume after end-of-day or a restart.
STATE_FILE = os.path.join(SCRIPT_DIR, "scraper_state.json")

# Lock file — stops two copies running at once (daily + on-startup triggers).
LOCK_FILE = os.path.join(SCRIPT_DIR, "scraper.lock")

# =============================================================
# OUTPUT CSV FIELDS
# =============================================================
# This is the canonical list of columns every scraper's CSV must have.
# All scrapers write the same columns so the Excel database can combine
# them without any reshaping. If a field doesn't apply to a site
# (e.g. country isn't shown on IC Source), the scraper writes "".
OUTPUT_FIELDS = [
    "scraped_at",
    "source",
    "search_part",
    "vendor",
    "part",
    "qty",
    "mfg",
    "dc",
    "price",
    "comment",
    "uploaded",
    "region",
    "inventory_type",
    "country",
]


# =============================================================
# IC SOURCE
# =============================================================
ICSOURCE_USER = "aeri"
ICSOURCE_PASS = "FindMyParts"


# =============================================================
# NET COMPONENTS
# =============================================================
NETCOMP_USER = "RobbH"
NETCOMP_PASS = "Aeri1234!n"
NETCOMP_ACCT = "339259"

# =============================================================
# CRM DATABASE (SQL Server)
# =============================================================
DB_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=aeri-sql-2019;"
    "DATABASE=CCCRM;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)