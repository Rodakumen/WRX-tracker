import time
import logging
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# Sette opp profesjonell logging til både fil og skjerm
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("tracker.log"),
        logging.StreamHandler()
    ]
)


def get_product_links_auto24(page) -> list:
    logging.info("Parsing auto24.ee links...")

    try:
        page.wait_for_selector("div.result-row", timeout=5000)
    except Exception:
        logging.warning("Fant ingen resultat-rader på auto24-siden.")
        return []

    anchors = page.locator("div.result-row a.row-link")
    relative_links = anchors.evaluate_all("elements => elements.map(e => e.getAttribute('href'))")
    base_url = "https://www.auto24.ee"
    return [urljoin(base_url, link) for link in relative_links if link]


def get_product_links_finn(page) -> list:
    logging.info("Parsing finn.no links...")
    anchors = page.locator("article.sf-search-ad a.sf-search-ad-link")
    links = anchors.evaluate_all("elements => elements.map(e => e.getAttribute('href'))")
    return [link for link in links if link]


def get_raw_html_and_links(urls: list) -> list:
    all_product_links = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for url in urls:
            logging.info(f"Extracting list index from {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)

                # Siden subaru-søk sjelden har 1000 sider, holder det ofte med et raskt scroll
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

                if "auto24.ee" in url:
                    all_product_links.extend(get_product_links_auto24(page))
                elif "finn.no" in url:
                    all_product_links.extend(get_product_links_finn(page))
            except Exception as e:
                logging.error(f"Error index-scraping {url}: {e}")

        context.close()
        browser.close()
    return all_product_links


# GIGANTISK OPPGRADERING: Vi åpner nettleseren EN gang, og looper igjennom alle bilene!
def get_bulk_pages_html(urls: list) -> list:
    """ Opens browser once and extracts multiple single car pages efficiently """
    payloads = []
    if not urls:
        return payloads

    logging.info(f"Starting bulk extraction of {len(urls)} car listings...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for index, url in enumerate(urls, 1):
            logging.info(f"[{index}/{len(urls)}] Extracting page: {url}")
            result = {"url": url, "html": "", "shadow_price": None}

            try:
                if "finn.no" in url:
                    page.goto(url, wait_until="networkidle", timeout=15000)
                    try:
                        page.wait_for_selector('[data-testid="price"]', timeout=3000)
                        result["shadow_price"] = page.locator('[data-testid="price"]').inner_text()
                    except Exception:
                        pass
                else:
                    page.goto(url, wait_until="domcontentloaded", timeout=10000)

                result["html"] = page.content()
                payloads.append(result)

                # Høflig skraping: Vent 0.5 sekunder mellom hver bil så vi ikke dundrer ned serverne deres
                time.sleep(0.5)

            except Exception as e:
                logging.warning(f"Failed to extract details for {url}: {e}")

        context.close()
        browser.close()

    return payloads


if __name__ == '__main__':
    # Test URLs for both platforms
    target_urls = [
        "https://www.auto24.ee/kasutatud/nimekiri.php?b=23&bw=1630&ae=3&ssid=274810213&_lv=aa0f254b3019bc215161b6ceda78ec5d",
        "https://www.finn.no/mobility/search/car?registration_class=1&variant=1.810.1368"
    ]

    # Gather everything into a single array
    gathered_links = get_raw_html_and_links(target_urls)

    print("\n--- Scraping Summary ---")
    print(f"Total product links gathered: {len(gathered_links)}")