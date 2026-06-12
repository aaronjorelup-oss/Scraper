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

from config import OUTPUT_DIR, SHOW_BROWSER, DB_CONNECTION_STRING
from scrapers import icsource_scraper
from scrapers import netcomponents_scraper


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================
# Where parts come from
# =============================================================

def get_parts_list():
    """
    Fetch unique part numbers from the CRM database.

    Connects to the CCCRM SQL Server database and queries the REQ table
    for all rows where AUTO_MATCH = 1, returning the unique trimmed part
    numbers from the FULLPART column.

    Falls back to input_parts.txt if the database is unreachable, so you
    can still run the scraper offline or for quick testing.

    Returns:
        List of unique part number strings, e.g. ["ISL95835IRZ", "LM317T", ...]
    """
    try:
        import pyodbc
    except ImportError:
        print("WARNING: pyodbc is not installed.")
        print("         Run: pip install pyodbc")
        print("         Falling back to input_parts.txt...\n")
        return _get_parts_from_file()

    try:
        print("Connecting to CRM database (aeri-sql-2019 / CCCRM)...")
        conn = pyodbc.connect(DB_CONNECTION_STRING, timeout=10)
        cursor = conn.cursor()

        # LTRIM + RTRIM trims any leading/trailing whitespace from FULLPART.
        # DISTINCT ensures we only scrape each unique part number once,
        # even if it appears on many requisition rows.
        cursor.execute("""
            SELECT DISTINCT LTRIM(RTRIM(FULLPART)) AS part_number
            FROM REQ
            WHERE AUTO_MATCH = 1
              AND FULLPART IS NOT NULL
              AND LTRIM(RTRIM(FULLPART)) <> ''
            ORDER BY part_number
        """)

        parts = [row.part_number for row in cursor.fetchall()]
        conn.close()

        print(f"  -> {len(parts)} unique part(s) loaded from database.")
        return parts

    except Exception as e:
        # Don't crash the whole run just because the DB is unavailable.
        # Print a clear warning and fall back to the text file.
        print(f"WARNING: Could not connect to the CRM database.")
        print(f"         Error: {e}")
        print(f"         Falling back to input_parts.txt...\n")
        return _get_parts_from_file()


def _get_parts_from_file():
    """
    Read part numbers from input_parts.txt (one per line).
    Used as a fallback when the database is unavailable, and for testing.
    """
    parts_file = os.path.join(SCRIPT_DIR, "input_parts.txt")

    if not os.path.exists(parts_file):
        print(f"ERROR: {parts_file} not found and database is unavailable.")
        print("       Create input_parts.txt with one part number per line,")
        print("       or ensure the CRM database is reachable.")
        return []

    with open(parts_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # Deduplicate (same logic as the SQL query) in case the file has repeats
    seen = set()
    parts = []
    for p in lines:
        if p not in seen:
            seen.add(p)
            parts.append(p)

    print(f"  -> {len(parts)} unique part(s) loaded from input_parts.txt.")
    return parts


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

    print(f"Loaded {len(parts)} part number(s) to scrape.")
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