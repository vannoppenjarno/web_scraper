# Modular Web Scraper 

## Overview
This pipeline scrapes company profile URLs and corresponding email addresses from company profile pages on **Europages** for a given sector (e.g., winery). It is designed to be **efficient, modular, and scalable**, while handling common obstacles like contact subpages, verification gates, and obfuscated emails.

To scrape other websites, some minimal information (urls, classes and a selector) must be manually gathered from the website's DOM.

---

## Features
- Extracts company profile links by sector.
- Visits company pages and parses emails.
- Follows "Contact" subpages when needed.
- Skips cookies/verification buttons when needed.
- Handles failures gracefully (logs companies even if no email found).
- Outputs two CSVs:
  - `links_<sector>.csv`: all company profile URLs
  - `emails_<sector>.csv`: company name, country, and extracted emails

---

## Scripts
- `main`: Master script to run pipeline
- `src/scraper.py`: Core scraping logic 
- `src/utils.py`: Helper functions (e.g., fetch html, extract hrefs and emails, contact page detection, etc.)

---

## Output
- `output/links_<sector>.csv` — List of company profile URLs.
- `output/emails_<sector>.csv` — List of company names, countries, and email addresses.

---

## Limitations
- Not all companies expose an email address.

---

## Run
```bash
pip install -r requirements.txt
python main.py