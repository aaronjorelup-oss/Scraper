"""
main_scraper.py - Orchestrator
================================
Reads a list of part numbers, then runs each dedicated scraper.
Each scraper saves its own CSV to the output/ folder independently,
so a failure in one scraper doesn't affect the others.

USAGE:
    python main_scraper.py

OUTPUT:
    output/icsource_results_YYYY-MM-DD_HHMMSS.csv
    output/netcomponents_results_YYYY-MM-DD_HHMMSS.csv
"""

import os
from datetime import datetime

from config import OUTPUT_DIR, SHOW_BROWSER
from scrapers import icsource_scraper
from scrapers import netcomponents_scraper


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================
# Where parts come from
# =============================================================

def get_parts_list():
    """
    Read part numbers to scrape.

    Currently reads from input_parts.txt (one per line).

    LATER: Replace this with a SQL Server query to your CRM.
    Example of what that will look like:

        import pyodbc
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=your_server;DATABASE=your_db;UID=...;PWD=...'
        )
        cursor = conn.cursor()
        cursor.execute('''
            SELECT TOP 10 FullPart
            FROM WebScraperParts
            WHERE WebScraped = 0
            ORDER BY Date_Scraped
        ''')
        return [row[0].strip() for row in cursor.fetchall()]
    """
    parts_file = os.path.join(SCRIPT_DIR, "input_parts.txt")

    if not os.path.exists(parts_file):
        print(f"ERROR: {parts_file} not found.")
        return []

    with open(parts_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# =============================================================
# Run a single scraper, with isolated error handling.
# =============================================================

def run_scraper(scraper_module, scraper_name, parts):
    """
    Run one scraper module and return its summary.
    If the whole scraper crashes, we catch it so other scrapers
    can still run.
    """
    print()
    print("=" * 60)
    print(f"RUNNING: {scraper_name}")
    print("=" * 60)
    try:
        summary = scraper_module.scrape(parts, show_browser=SHOW_BROWSER)
        print()
        print(f"  Parts searched: {summary['parts_searched']}")
        print(f"  Rows written:   {summary['rows_written']}")
        print(f"  Errors:         {summary['errors']}")
        print(f"  CSV:            {os.path.basename(summary['filepath'])}")
        return summary
    except Exception as e:
        print(f"  FATAL: {scraper_name} crashed: {e}")
        return {
            "filepath": None,
            "parts_searched": 0,
            "rows_written": 0,
            "errors": len(parts),
        }


# =============================================================
# Main
# =============================================================

def main():
    print()
    print("#" * 60)
    print("# AERI MAIN SCRAPER")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#" * 60)
    print()

    parts = get_parts_list()
    if not parts:
        print("No parts to search. Exiting.")
        return

    print(f"Loaded {len(parts)} part numbers.")
    print(f"Output directory: {OUTPUT_DIR}")

    # Run each scraper. They write their own CSVs and are fully
    # independent - if one crashes, the next one still runs.
    summaries = []
    summaries.append(
        ("IC Source", run_scraper(icsource_scraper, "IC Source", parts))
    )
    summaries.append(
        ("NetComponents", run_scraper(
            netcomponents_scraper, "NetComponents", parts
        ))
    )

    # Final summary
    print()
    print("=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    for name, s in summaries:
        status = "OK" if s["filepath"] else "FAILED"
        print(
            f"  [{status}] {name:15s} "
            f"parts={s['parts_searched']:>3d}  "
            f"rows={s['rows_written']:>4d}  "
            f"errors={s['errors']:>2d}"
        )
    print()


if __name__ == "__main__":
    main()
