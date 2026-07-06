# Datacenter News Scraper

This scraper fetches site-level information and news coverage of most US datacenters.

- Publicly accessible site data comes from  [datacenters.com](https://datacenters.com)
- News feed information sourced Google News via Search API

To run the scraper:

1. Set `SEARCH_API_KEY` in `.env`

2. ```python pip install -r requirements.txt```

3. ```python main.py```

If rate limiting occurs, wait a bit and rerun the script.

---

How it works:

### 1. Get Listing URLs

~4,000 US data center listing URLs are scraped synchronously via Playwright.

### 2. Scrape Listings

URLs returned from step 1 are scraped asynchronously via Playwright. Data comes from page HTML and React props.

### 3. Fetch News Feeds

Google News is queried via Search API to get articles mentioning the data center project's provider, city, and other
attributes. Attempts to filter out job listings and other unrelated articles.

### 4. Scrape Articles

Article URLs returned from step 3 are scraped asynchronously via Playwright to get full text, attempting to detect
sources with bot-protection.

### 5. Checkpointing & Resumption

Data is safely written immediately after it is returned. If at any point the scraper exits (errors out or is
terminated), upon resumption, the bot will skip over already scraped data, with the exception of items which failed due
to page timeouts.