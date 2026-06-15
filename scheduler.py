import logging
from apscheduler.schedulers.background import BackgroundScheduler
from models import TrackedItem, PriceHistory, User
from db import db
from scrapers import scrape_product
from notifications import notify_price_drop
from config import Config
from datetime import datetime

logger = logging.getLogger(__name__)

def check_all_prices():
    logger.info("Starting scheduled background price check run...")
    
    # Needs to be called within an app_context which is provided by the wrapper job.
    items = TrackedItem.query.filter_by(status='active').all()

    for item in items:
        process_item(item)
    
    logger.info("Scheduled price check completed.")

def process_item(item):
    item_id = item.id
    url = item.url
    user_email = item.user.email
    alert_mode = item.alert_mode
    alert_target = item.alert_target
    lowest_price = item.lowest_price if item.lowest_price else float('inf')
    highest_price = item.highest_price if item.highest_price else 0
    initial_price = item.initial_price
    
    logger.info(f"Checking item ID {item_id}: {item.product_name}")
    
    scraped_data = scrape_product(url)
    
    if not scraped_data or scraped_data.get('error') or scraped_data.get('price') is None:
        item.consecutive_errors += 1
        logger.warning(f"Scrape failed for item {item_id}. Consecutive errors: {item.consecutive_errors}")
        
        if item.consecutive_errors >= 5:
            item.status = 'error'
            
        item.last_checked = datetime.utcnow()
        db.session.commit()
        return

    current_price = scraped_data['price']
    
    # Update metrics
    new_lowest = min(lowest_price, current_price)
    new_highest = max(highest_price, current_price)
    
    # Store price history
    new_history = PriceHistory(item_id=item_id, price=current_price)
    db.session.add(new_history)

    # Evaluate target based on alert mode
    target_hit = False
    if alert_mode == 'absolute':
        target_hit = current_price <= alert_target
    elif alert_mode == 'percentage':
        drop_threshold = initial_price * (1.0 - alert_target)
        target_hit = current_price <= drop_threshold

    if target_hit:
        logger.info(f"Target hit for item {item_id}! Triggering alert.")
        notify_price_drop(user_email, item.product_name, url, lowest_price if lowest_price != float('inf') else current_price, current_price, scraped_data.get('image_url'))
        item.status = 'triggered'

    item.current_price = current_price
    item.lowest_price = new_lowest
    item.highest_price = new_highest
    item.consecutive_errors = 0
    item.last_checked = datetime.utcnow()
    
    db.session.commit()

def start_scheduler(app):
    scheduler = BackgroundScheduler()
    interval = Config.SCHEDULER_INTERVAL_MINUTES
    
    def job_wrapper():
        with app.app_context():
            check_all_prices()
            
    scheduler.add_job(func=job_wrapper, trigger="interval", minutes=interval, id='price_check_job')
    scheduler.start()
    logger.info(f"APScheduler started. Job interval: {interval} minutes.")
