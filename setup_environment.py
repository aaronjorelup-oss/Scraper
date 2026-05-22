"""
setup_environment.py - One-time environment setup
==================================================
Run this ONCE on a new machine to get everything the scraper needs:

    1. Creates a virtual environment in a folder called ".venv"
    2. Installs Playwright into that virtual environment
    3. Downloads the Chromium browser that Playwright drives

After this finishes, you activate the virtual environment and run the
scraper as usual (instructions are printed at the end).

USAGE:
    python setup_environment.py

This works on both Windows and Mac/Linux. It figures out the right
paths for whichever one you're on.
"""

import os
import sys
import subprocess
import venv


# =============================================================
# Settings
# =============================================================

# Name of the folder the virtual environment lives in.
# The leading dot keeps it tidy/hidden; ".venv" is the common convention.
VENV_DIR = ".venv"

# Packages to install with pip. Playwright is all the scraper needs today.
# When you wire main_scraper.py up to SQL Server later, add "pyodbc" here
# and re-run this script.
PACKAGES = [
    "playwright",
    # "pyodbc",   # <- uncomment when you connect to the CRM database
]

# Which Playwright browser(s) to download. The scraper only uses Chromium.
PLAYWRIGHT_BROWSERS = ["chromium"]


# =============================================================
# Helpers
# =============================================================

def run(command, description):
    """
    Run a shell command, printing it first. Stops the script with a
    clear message if the command fails, so you're never left guessing.
    """
    print(f"\n>>> {description}")
    print(f"    {' '.join(command)}")
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"\nERROR: that step failed (exit code {result.returncode}).")
        print("Setup stopped. Fix the error above and run this script again.")
        sys.exit(1)


def venv_python_path(venv_dir):
    """
    Return the path to the Python executable INSIDE the virtual env.
    Windows puts it in Scripts\\, Mac/Linux put it in bin/.
    """
    if os.name == "nt":  # Windows
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def activation_hint(venv_dir):
    """Return the command the user types to activate the venv, per OS."""
    if os.name == "nt":
        return f"{venv_dir}\\Scripts\\activate"
    return f"source {venv_dir}/bin/activate"


# =============================================================
# Main
# =============================================================

def main():
    # Run from the folder this script lives in, so .venv is created
    # right next to main_scraper.py no matter where you launch from.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    print("#" * 60)
    print("# AERI SCRAPER - ENVIRONMENT SETUP")
    print("#" * 60)
    print(f"Working in: {script_dir}")
    print(f"Python:     {sys.version.split()[0]} ({sys.executable})")

    # --- Check Python version (Playwright needs 3.8+) ---
    if sys.version_info < (3, 8):
        print("\nERROR: Python 3.8 or newer is required.")
        print("Install a newer Python and run this script again.")
        sys.exit(1)

    # --- Step 1: Create the virtual environment ---
    if os.path.exists(VENV_DIR):
        print(f"\n>>> Virtual environment '{VENV_DIR}' already exists - "
              f"reusing it.")
    else:
        print(f"\n>>> Creating virtual environment in '{VENV_DIR}'...")
        # with_pip=True ensures pip is available inside the new venv
        venv.create(VENV_DIR, with_pip=True)
        print("    Done.")

    py = venv_python_path(VENV_DIR)
    if not os.path.exists(py):
        print(f"\nERROR: expected Python at '{py}' but it isn't there.")
        print("The virtual environment may not have been created correctly.")
        sys.exit(1)

    # --- Step 2: Upgrade pip, then install packages ---
    # Always call pip via "python -m pip" using the venv's python, so we
    # know we're installing INTO the venv and not the system Python.
    run([py, "-m", "pip", "install", "--upgrade", "pip"],
        "Upgrading pip inside the virtual environment")

    run([py, "-m", "pip", "install", *PACKAGES],
        f"Installing packages: {', '.join(PACKAGES)}")

    # --- Step 3: Download the Chromium browser for Playwright ---
    run([py, "-m", "playwright", "install", *PLAYWRIGHT_BROWSERS],
        f"Downloading Playwright browser(s): "
        f"{', '.join(PLAYWRIGHT_BROWSERS)}")

    # --- Done ---
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print("\nNext time you want to run the scraper:\n")
    print(f"  1. Activate the virtual environment:")
    print(f"       {activation_hint(VENV_DIR)}")
    print(f"\n  2. Run the scraper:")
    print(f"       python main_scraper.py")
    print(f"\n  3. When you're done, leave the environment with:")
    print(f"       deactivate")
    print()


if __name__ == "__main__":
    main()