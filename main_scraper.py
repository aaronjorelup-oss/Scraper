"""
main_scraper.py - Orchestrator + Scheduler
===========================================
Pulls part numbers from the CRM, then scrapes them in small batches with a
polite pause between each batch. Designed to be "set and forget":

  * Runs only during configured operating hours.
  * Saves its progress to scraper_state.json after every batch, so it can
    pick up exactly where it left off after the end of the day OR after a
    computer restart.
  * Uses a lock file so two copies never run at the same time (the daily
    trigger and the on-startup trigger can't collide).

WHAT COUNTS AS A "CYCLE":
  One cycle = one fresh pull of the parts list from the database, processed
  all the way to the end. A cycle can span multiple days. Only when a cycle
  is fully finished does the next run pull a brand-new list from the DB.

USAGE:
    python main_scraper.py

OUTPUT:
    Each batch produces its own timestamped CSVs in output/, e.g.
        output/icsource_results_2026-06-12_090015.csv
        output/netcomponents_results_2026-06-12_090015.csv
    (So you'll see several small CSV pairs per day instead of one big pair.)
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, date, timedelta

from config import (
    SHOW_BROWSER,
    DB_CONNECTION_STRING,
    PARTS_PER_BATCH,
    BATCH_PAUSE_MINUTES,
    BUSINESS_HOURS_START,
    BUSINESS_HOURS_END,
    MAX_PARTS_PER_CYCLE,
    STATE_FILE,
    LOCK_FILE,
)
from scrapers import icsource_scraper
from scrapers import netcomponents_scraper


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================
# Where parts come from  (unchanged from your DB version)
# =============================================================

def get_parts_list():
    """
    Fetch unique part numbers from the CRM database.

    Connects to the CCCRM SQL Server database and queries the REQ table for
    all rows where AUTO_MATCH = 1, returning the unique trimmed part numbers
    from the FULLPART column. Falls back to input_parts.txt if the database
    is unreachable, so you can still run offline or for quick testing.
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

        # LTRIM + RTRIM trims any whitespace; DISTINCT keeps each part once.
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
        print("WARNING: Could not connect to the CRM database.")
        print(f"         Error: {e}")
        print("         Falling back to input_parts.txt...\n")
        return _get_parts_from_file()


def _get_parts_from_file():
    """Read part numbers from input_parts.txt (one per line). Fallback only."""
    path = os.path.join(SCRIPT_DIR, "input_parts.txt")
    if not os.path.exists(path):
        print(f"WARNING: {path} not found. No parts to scrape.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        parts = [line.strip() for line in f if line.strip()]
    print(f"  -> {len(parts)} part(s) loaded from input_parts.txt.")
    return parts


# =============================================================
# Single-instance lock
# =============================================================
# Two Task Scheduler triggers (daily + on-startup) could try to run at the
# same time. The lock file makes the second one notice the first and exit.

def acquire_lock():
    """Return True if we got the lock, False if another run is already active."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
        except Exception:
            print("Lock file was unreadable; treating it as stale and clearing it.")
            old_pid = None

        if old_pid is not None and _pid_is_running(old_pid):
            print(f"Another scraper is already running (PID {old_pid}). Exiting.")
            return False
        else:
            print("Found a leftover lock from a crashed run. Clearing it.")

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    """Remove the lock file. Safe to call even if it's already gone."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def _pid_is_running(pid):
    """Windows-friendly check for whether a process ID is still alive."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True,
        )
        return str(pid) in result.stdout
    except Exception:
        # If we can't tell, assume it's NOT running so we never deadlock
        # ourselves out of every future run because of one bad lock file.
        return False


# =============================================================
# State file (the part that makes resume possible)
# =============================================================

def load_state():
    """Return the saved state dict, or None if there's no state file yet."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARNING: Could not read state file ({e}). Starting fresh.")
        return None


def save_state(state):
    """Write the state dict to disk. Called after every batch."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def start_new_cycle():
    """Pull a fresh list from the DB and build a brand-new state object."""
    parts = get_parts_list()

    # Safety ceiling so a runaway DB result can never blow up the run.
    if MAX_PARTS_PER_CYCLE is not None and len(parts) > MAX_PARTS_PER_CYCLE:
        print(f"Capping list at {MAX_PARTS_PER_CYCLE} parts "
              f"(database returned {len(parts)}).")
        parts = parts[:MAX_PARTS_PER_CYCLE]

    state = {
        "cycle_date": date.today().isoformat(),
        "parts_list": parts,
        "next_index": 0,
        "completed": False,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "last_batch_at": None,
    }
    save_state(state)
    return state


def decide_state():
    """
    Work out whether to start fresh, resume, or do nothing.

    Returns a state dict to work on, or None if there's nothing to do.
    """
    today = date.today().isoformat()
    state = load_state()

    if state is None:
        print("No previous progress found. Starting a new cycle.")
        return start_new_cycle()

    if not state.get("completed", False):
        done = state.get("next_index", 0)
        total = len(state.get("parts_list", []))
        print(f"Resuming previous cycle from {state.get('cycle_date')} "
              f"({done} of {total} parts already done).")
        return state

    # Previous cycle was completed.
    if state.get("cycle_date") != today:
        print("Previous cycle finished on an earlier day. Starting a new cycle.")
        return start_new_cycle()

    print("Today's cycle is already complete. Nothing to do.")
    return None


# =============================================================
# Operating-hours helpers
# =============================================================

def before_hours(now):
    return now.hour < BUSINESS_HOURS_START


def after_hours(now):
    return now.hour >= BUSINESS_HOURS_END


# =============================================================
# The main batch loop
# =============================================================

def run_batches(state):
    parts = state["parts_list"]
    total = len(parts)

    if total == 0:
        print("Parts list is empty. Nothing to scrape.")
        state["completed"] = True
        save_state(state)
        return

    while True:
        now = datetime.now()

        # --- Operating-hours gate ---------------------------------------
        if before_hours(now):
            # E.g. an on-startup trigger fired at 3 AM after a reboot.
            # Don't scrape outside hours; the daily trigger will resume.
            print(f"It's before {BUSINESS_HOURS_START}:00. Exiting; "
                  f"the next scheduled run will resume.")
            return
        if after_hours(now):
            print(f"It's past {BUSINESS_HOURS_END}:00. Saving progress and "
                  f"exiting; the next run will resume where we left off.")
            return

        # --- Slice out the next batch -----------------------------------
        i = state["next_index"]
        batch = parts[i:i + PARTS_PER_BATCH]
        if not batch:
            state["completed"] = True
            save_state(state)
            print("Cycle complete - all parts have been scraped.")
            return

        print("\n" + "=" * 60)
        print(f"Batch: parts {i + 1}-{i + len(batch)} of {total}")
        print("=" * 60)

        # Each scraper is fault-isolated and writes its own CSV. We wrap
        # them anyway so one site's failure can't stop the other or the loop.
        try:
            icsource_scraper.scrape(batch, show_browser=SHOW_BROWSER)
        except Exception as e:
            print(f"  IC Source batch error: {e}")
        try:
            netcomponents_scraper.scrape(batch, show_browser=SHOW_BROWSER)
        except Exception as e:
            print(f"  NetComponents batch error: {e}")

        # --- Advance and SAVE before pausing ----------------------------
        # Persisting here (not after the sleep) is what makes a crash during
        # the pause harmless: next_index already reflects the finished batch.
        state["next_index"] = i + len(batch)
        state["last_batch_at"] = now.isoformat(timespec="seconds")
        if state["next_index"] >= total:
            state["completed"] = True
        save_state(state)

        if state["completed"]:
            print("\nCycle complete - all parts have been scraped.")
            return

        # --- Pause, unless the next batch would fall outside hours -------
        next_start = now + timedelta(minutes=BATCH_PAUSE_MINUTES)
        if after_hours(next_start) or next_start.day != now.day:
            print(f"\nNext batch would fall outside operating hours. "
                  f"Exiting; the next run will resume.")
            return

        print(f"\nPausing {BATCH_PAUSE_MINUTES} minutes before the next batch...")
        time.sleep(BATCH_PAUSE_MINUTES * 60)


# =============================================================
# Entry point
# =============================================================

def main():
    print("AERI Scraper starting at "
          f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not acquire_lock():
        sys.exit(0)

    try:
        state = decide_state()
        if state is not None:
            run_batches(state)
    finally:
        # Always release the lock, even if something blew up mid-run.
        release_lock()
        print("Scraper run finished.")


if __name__ == "__main__":
    main()