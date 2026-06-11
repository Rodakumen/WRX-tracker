import time
import logging
from Load import load_data

# Config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("tracker.log"), logging.StreamHandler()]
)

IF_HOURS = 1  # Amount of times per check
DELAY_SECONDS = IF_HOURS * 3600

if __name__ == "__main__":
    logging.info("🚀 WRX Tracker Pipeline initializing...")

    while True:
        try:
            logging.info("🔄 Triggered a new datacheck...")
            load_data()
            logging.info(f"😴 Check done. Waiting for {IF_HOURS} hours until next check...")
        except Exception as e:
            logging.critical(f"🚨 Critical issue in the scraping-engine: {e}")

        time.sleep(DELAY_SECONDS)