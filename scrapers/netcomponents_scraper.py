"""
netcomponents_scraper.py - Dedicated NetComponents scraper
===========================================================
Logs into NetComponents, searches each part, extracts results, and
writes them to its own timestamped CSV file in the output folder.

Public interface:
    scrape(parts_list, show_browser=True) -> summary dict
"""

import os
import csv
import time
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    NETCOMP_USER,
    NETCOMP_PASS,
    NETCOMP_ACCT,
    OUTPUT_DIR,
    OUTPUT_FIELDS,
    DELAY_BETWEEN_SEARCHES,
)


SOURCE_NAME = "NetComponents"


# =============================================================
# Internal helpers
# =============================================================

def _login(page):
    """Log into NetComponents."""
    page.goto("https://www.netcomponents.com/account/login", timeout=30000)
    time.sleep(3)

    page.locator("#AccountNumber").fill(NETCOMP_ACCT)
    page.locator("#UserName").fill(NETCOMP_USER)
    page.locator("#Password").fill(NETCOMP_PASS)
    page.locator("input[type='button'][value='Login']").click()
    time.sleep(6)


def _search_and_extract(page, part_number):
    """Search a single part on NetComponents, return list of result dicts."""
    encoded_part = urllib.parse.quote(part_number, safe="")
    search_url = (
        f"https://www.netcomponents.com/search/result?"
        f"SearchLogic=Begins&PSA=true"
        f"&PartsSearched%5B0%5D.PartNumber={encoded_part}"
    )
    page.goto(search_url, timeout=30000)

    try:
        page.wait_for_selector("table.searchresultstable", timeout=15000)
    except Exception:
        return []

    time.sleep(2)

    # Walk the table top-to-bottom, tracking the current region and
    # inventory type. Region rows have class="region-header", stock-type
    # rows have class="stocktype-header". Every data row that follows
    # inherits whatever was last seen.
    return page.evaluate("""
        () => {
            const table = document.querySelector('table.searchresultstable');
            if (!table) return [];

            const headerRow = table.rows[0];
            if (!headerRow) return [];

            // Build a column-name -> index map from the header row
            const headers = [];
            for (const c of headerRow.cells) {
                headers.push(c.textContent.trim().toLowerCase());
            }

            const findCol = (keyword) => {
                for (let i = 0; i < headers.length; i++) {
                    if (headers[i].includes(keyword.toLowerCase())) return i;
                }
                return -1;
            };

            const colPart = findCol('part');
            const colMfr = findCol('mfr');
            const colDC = findCol('dc');
            const colDesc = findCol('description');
            const colUploaded = findCol('uploaded');
            const colCtr = findCol('ctr');
            const colQty = findCol('qty');
            const colSupplier = findCol('supplier');

            const results = [];
            let currentRegion = '';
            let currentInventoryType = '';

            for (let i = 0; i < table.rows.length; i++) {
                const row = table.rows[i];

                // ---- Region header ----
                if (row.classList.contains('region-header')) {
                    currentRegion = row.textContent.trim();
                    continue;
                }

                // ---- Stock type header ----
                if (row.classList.contains('stocktype-header')) {
                    const stEl = row.querySelector('.stock-type');
                    const stText = stEl
                        ? stEl.textContent.trim().toLowerCase()
                        : '';
                    if (stText.includes('in-stock') ||
                        stText.includes('in stock')) {
                        currentInventoryType = 'Stock';
                    } else if (stText.includes('broker')) {
                        currentInventoryType = 'Broker';
                    } else {
                        currentInventoryType = stEl
                            ? stEl.textContent.trim() : '';
                    }
                    continue;
                }

                // ---- Data row ----
                const cells = row.cells;
                // Skip header row (i=0) and any rows that are too short
                if (i === 0) continue;
                if (cells.length < headers.length - 2) continue;

                const getText = (idx) => {
                    if (idx < 0 || idx >= cells.length) return '';
                    return (cells[idx].textContent || '').trim();
                };

                const part = getText(colPart);
                const vendor = getText(colSupplier);

                if (!part || part.length < 2) continue;

                results.push({
                    vendor: vendor,
                    part: part,
                    qty: getText(colQty),
                    dc: getText(colDC),
                    mfg: getText(colMfr),
                    comment: getText(colDesc),
                    uploaded: getText(colUploaded),
                    price: '',
                    region: currentRegion,
                    inventory_type: currentInventoryType,
                    country: getText(colCtr),
                });
            }

            return results;
        }
    """)


# =============================================================
# Public interface
# =============================================================

def scrape(parts_list, show_browser=True):
    """
    Scrape parts from NetComponents and write results to a CSV file.

    Args:
        parts_list: list of part number strings
        show_browser: True to show the browser, False to run headless

    Returns:
        Summary dict with: filepath, parts_searched, rows_written, errors
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"netcomponents_results_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    parts_searched = 0
    rows_written = 0
    errors = 0

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        f.flush()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=not show_browser,
                slow_mo=200 if show_browser else 0,
            )
            page = browser.new_page(viewport={"width": 1400, "height": 900})

            try:
                print(f"  [{SOURCE_NAME}] Logging in...")
                _login(page)
                print(f"  [{SOURCE_NAME}] Login complete.")

                for part in parts_list:
                    print(f"  [{SOURCE_NAME}] Searching: {part}")
                    try:
                        results = _search_and_extract(page, part)

                        timestamp_str = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        for r in results:
                            r["scraped_at"] = timestamp_str
                            r["source"] = SOURCE_NAME
                            r["search_part"] = part
                            writer.writerow(
                                {k: r.get(k, "") for k in OUTPUT_FIELDS}
                            )
                            rows_written += 1

                        f.flush()
                        parts_searched += 1
                        print(f"    -> {len(results)} results")

                    except Exception as e:
                        errors += 1
                        print(f"    -> ERROR: {e}")

                    time.sleep(DELAY_BETWEEN_SEARCHES)

            finally:
                browser.close()

    return {
        "filepath": filepath,
        "parts_searched": parts_searched,
        "rows_written": rows_written,
        "errors": errors,
    }


# =============================================================
# Run standalone for testing
# =============================================================
if __name__ == "__main__":
    test_parts = ["ISL95835IRZ", "K4A8G085WB-BIRCTCT", "ATT303070M68I"]
    print(f"Testing NetComponents scraper with {len(test_parts)} parts...")
    summary = scrape(test_parts, show_browser=True)
    print()
    print(f"Summary: {summary}")
