import logging
from app import app
from scheduler import check_all_prices

# Set up logging so you can see the scraper working in the Render logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Manual scraper script triggered by Render.")
    
    # We must use app.context() so the database knows which Flask app to connect to
    with app.app_context():
        check_all_prices()
        
    logger.info("Scraping cycle complete. Shutting down script.")