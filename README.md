# AERI Web Scraper

Stand-alone web scraper that searches part numbers on IC Source and
NetComponents and saves the results to CSV files.

## Folder Structure

```
WebScraper/
├── main_scraper.py              <- The orchestrator. Run this.
├── config.py                    <- Credentials and settings
├── input_parts.txt              <- List of parts to search (one per line)
├── output/                      <- CSV files land here
└── scrapers/
    ├── __init__.py              <- (Empty - makes 'scrapers' a Python package)
    ├── icsource_scraper.py      <- IC Source dedicated scraper
    └── netcomponents_scraper.py <- NetComponents dedicated scraper
```

## How to Use

### Daily run (the normal case):
```
python main_scraper.py
```

This reads parts from `input_parts.txt`, runs each scraper, and saves
the results to timestamped CSVs in the `output/` folder.

### Test a single scraper:
Each scraper can run on its own for testing/debugging:
```
python -m scrapers.icsource_scraper
python -m scrapers.netcomponents_scraper
```

### Update credentials:
Edit `config.py`. All credentials live in one place.

### Add or remove parts:
Edit `input_parts.txt`. One part number per line.

## Architecture Notes

Each scraper exposes the same simple interface:

```python
results = icsource_scraper.scrape(parts_list, show_browser=True)
```

It returns a list of dicts, each with these keys:
`source, search_part, vendor, part, qty, mfg, dc, price, comment, uploaded, scraped_at`

This means adding a new scraper later (like Octopart or Findchips) is just
a matter of creating a new file in `scrapers/` that exposes a `scrape()`
function with the same signature.

## To Do

- Connect `main_scraper.py` to the CRM's SQL Server (replace `get_parts_list()`)
- Add scheduling logic (10 parts every 30 min)
- Set up as a Windows scheduled task / cron job
