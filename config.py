"""
config.py - Centralized configuration
======================================
All credentials, settings, and the canonical CSV field list live here.
NEVER commit this file to a public repo (or share it).
"""

import os

# Folder where the scraper CSVs will be saved.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

# Whether to show the browser while scraping.
# True  = visible browser (good for debugging)
# False = headless (faster, runs in background, use for cron jobs)
SHOW_BROWSER = True

# How many seconds to wait between part searches (be polite to the sites)
DELAY_BETWEEN_SEARCHES = 1


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
