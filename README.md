# Modular Web Scraper 

## Overview
This pipeline scrapes company profile URLs and corresponding email addresses as demonstrated for European wine producers on Europages.

## Scripts
- `extract_links.py`: Script to extract and collect company profile links by crawling a given URL.
- `extract_emails.py`: Extracts emails from those profiles or externally linked websites.
- `main.py`: Master script to run pipeline

## Output
- `data/links_<sector>.csv` — List of profile URLs.
- `data/emails_<sector>.csv` — List of names, countries, and verified email addresses.

## Run
```bash
pip install -r requirements.txt
python main.py