# WRX Tracker 🚗
Automated ETL pipeline that monitors Subaru WRX/STI listings across finn.no 
and auto24.ee, tracks price changes, and sends email alerts when new cars 
appear or prices drop.

## How it works
Extract → Transform → Load → Alert
- **Extract** — Playwright launches a headless browser and scrapes listing pages on finn.no and auto24.ee, collecting all individual car URLs. It then visits each car page and pulls the raw HTML.
- **Transform** — BeautifulSoup parses the raw HTML from each site, pulling out the relevant fields: title, price, mileage, year, engine size and power output. Each site has its own parser since the HTML structure is different.
- **Load** — The cleaned data is inserted into a PostgreSQL database running in Docker. If a car already exists (matched by URL), it updates the record instead. If the price has changed since last run, it flags it.
- **Alert** — If a car is brand new or its price has dropped, an HTML email with the car's image, specs and a direct link to the listing is sent via Gmail SMTP.

The pipeline runs in a loop via `main.py`, checking every hour automatically.

## Email Alert Preview
![Email notification example](assets/email_preview.png)

## Tech stack
- Python, PostgreSQL, Docker
- Playwright, BeautifulSoup, psycopg2
- SMTP email notifications

## Setup
1. Copy `.env.example` to `.env` and fill in your credentials
2. Run `docker-compose up -d` to start the database
3. Run `python main.py` to start the tracker

## What I learned
Building this project taught me how to design an **idempotent ETL pipeline** — meaning the scraper can run repeatedly without creating duplicate data or false alerts. I learned how Playwright handles dynamic JavaScript-rendered pages that traditional scrapers can't reach, and how to structure a PostgreSQL schema around a `UNIQUE` constraint to detect price changes over time. I also got hands-on experience with Docker for running a local database, and managing sensitive credentials safely through environment variables instead of hardcoding them.
