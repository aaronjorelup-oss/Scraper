"""
icsource_scraper.py - Dedicated IC Source scraper
==================================================
Logs into IC Source, searches each part, extracts results, and writes
them to its own timestamped CSV file in the output folder.

Public interface:
    scrape(parts_list, show_browser=True) -> summary dict

The summary dict contains:
    filepath:        path to the CSV that was written
    parts_searched:  how many parts we successfully searched
    rows_written:    how many result rows ended up in the CSV
    errors:          how many parts errored out
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
    ICSOURCE_USER,
    ICSOURCE_PASS,
    OUTPUT_DIR,
    OUTPUT_FIELDS,
    DELAY_BETWEEN_SEARCHES,
)


SOURCE_NAME = "ICSource"


# =============================================================
# Internal helpers
# =============================================================

def _login(page):
    """Log into IC Source."""
    page.goto("https://www.icsource.com/", timeout=30000)
    time.sleep(2)

    page.locator("#ctl00_cphBody_txtUsername").fill(ICSOURCE_USER)

    # Hidden password field - reveal via JavaScript first
    page.evaluate("""
        () => {
            const pw = document.querySelector('#ctl00_cphBody_txtPassword');
            if (pw) {
                let el = pw;
                while (el && el !== document.body) {
                    el.style.display = '';
                    el.style.visibility = 'visible';
                    el.style.opacity = '1';
                    el.style.height = 'auto';
                    el.style.overflow = 'visible';
                    el = el.parentElement;
                }
            }
        }
    """)
    time.sleep(0.5)

    page.locator("#ctl00_cphBody_txtPassword").fill(
        ICSOURCE_PASS, force=True
    )
    page.locator("#ctl00_cphBody_txtPassword").press("Enter")
    time.sleep(5)


def _search_and_extract(page, part_number):
    """Search a single part, return a list of result dicts."""
    encoded_part = urllib.parse.quote(part_number, safe="")
    search_url = (
        f"https://www.icsource.com/members/Search/SearchNew2025.aspx"
        f"?part={encoded_part}"
    )
    page.goto(search_url, timeout=30000)

    try:
        page.wait_for_selector("table.tblResults", timeout=15000)
    except Exception:
        return []

    time.sleep(2)

    # Walk the table top-to-bottom, tracking the current section.
    # Every <tr class="groupRow"> establishes a new region/inventory_type
    # for all subsequent data rows until the next groupRow.
    return page.evaluate("""
        () => {
            const table = document.querySelector('table.tblResults');
            if (!table) return [];

            const results = [];
            let currentRegion = '';
            let currentInventoryType = '';

            for (const row of table.querySelectorAll('tr')) {
                // ---- Section header ----
                if (row.classList.contains('groupRow')) {
                    // Format: "Region - Match Type - Stock Type"
                    // e.g. "North America - Exact Match - Available"
                    //      "Europe - Exact Match - Stock"
                    const text = row.textContent.trim();
                    const parts = text.split(' - ').map(s => s.trim());
                    if (parts.length >= 3) {
                        currentRegion = parts[0];
                        // Last part has the stock type, possibly with
                        // trailing whitespace from icon spans
                        const stockTypeText = parts[parts.length - 1]
                            .toLowerCase();
                        if (stockTypeText.includes('stock')) {
                            currentInventoryType = 'Stock';
                        } else if (stockTypeText.includes('available')) {
                            currentInventoryType = 'Broker';
                        } else {
                            currentInventoryType = parts[parts.length - 1];
                        }
                    }
                    continue;
                }

                // ---- Data row ----
                const vendorCell = row.querySelector('.tdCompanyName');
                if (!vendorCell) continue;  // Not a real result row

                const vendorLink = vendorCell.querySelector('a');
                const vendor = vendorLink
                    ? vendorLink.textContent.trim()
                    : vendorCell.textContent.trim();

                const partCell = row.querySelector('.fieldPart');
                const part = partCell ? partCell.textContent.trim() : '';

                const qtyCell = row.querySelector(
                    'td.resultsdontshowon900.noWrap.txtRight:not(.txtCenter)'
                );
                const qty = qtyCell ? qtyCell.textContent.trim() : '';

                const mfgDiv = row.querySelector('.fieldMfg');
                const mfg = mfgDiv ? mfgDiv.textContent.trim() : '';

                // Date code
                let dc = '';
                const starsCell = row.querySelector('.tdStars');
                if (starsCell) {
                    let nextCell = starsCell.nextElementSibling;
                    if (nextCell &&
                        !nextCell.classList.contains('FranchiseTag')) {
                        const text = nextCell.textContent.trim();
                        if (text && !text.includes('Star') &&
                            text.length < 30) {
                            dc = text;
                        }
                    }
                }

                const commentDiv = row.querySelector('.fieldComment');
                const comment = commentDiv
                    ? commentDiv.textContent.trim() : '';

                let uploaded = '';
                const uploadedPopups = row.querySelectorAll(
                    '[id^="divUploaded"]'
                );
                if (uploadedPopups.length > 0) {
                    const wrapper = uploadedPopups[0].closest(
                        '.divDetailWrapper2025'
                    );
                    if (wrapper) {
                        const dateDiv = wrapper.querySelector(
                            'div:not(.divDetailPopup2025)'
                        );
                        if (dateDiv) uploaded = dateDiv.textContent.trim();
                    }
                }

                results.push({
                    vendor: vendor,
                    part: part,
                    qty: qty,
                    dc: dc,
                    mfg: mfg,
                    comment: comment,
                    uploaded: uploaded,
                    price: '',
                    region: currentRegion,
                    inventory_type: currentInventoryType,
                    country: '',  // Not shown in IC Source grid
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
    Scrape parts from IC Source and write results to a CSV file.

    Args:
        parts_list: list of part number strings
        show_browser: True to show the browser, False to run headless

    Returns:
        Summary dict with: filepath, parts_searched, rows_written, errors
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"icsource_results_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    parts_searched = 0
    rows_written = 0
    errors = 0

    # Open the CSV first so we always have a file even if the browser
    # crashes immediately. We flush after each part so partial results
    # are saved if something goes wrong mid-batch.
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

                        f.flush()  # Save after each part
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
    test_parts = ["ISL95835IRZ", "RJE741881310T", "ZDU0110RFX"]
    print(f"Testing IC Source scraper with {len(test_parts)} parts...")
    summary = scrape(test_parts, show_browser=True)
    print()
    print(f"Summary: {summary}")
