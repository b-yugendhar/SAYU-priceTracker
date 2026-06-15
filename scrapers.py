import time
import logging
import re
from functools import wraps
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Simple In-Memory Cache ---
CACHE = {}
CACHE_EXPIRY = 300  # 5 minutes

def get_cached_result(url):
    if url in CACHE:
        result, timestamp = CACHE[url]
        if time.time() - timestamp < CACHE_EXPIRY:
            logger.info(f"Returning cached result for {url}")
            return result
        else:
            del CACHE[url]
    return None

def set_cache_result(url, result):
    CACHE[url] = (result, time.time())

# --- Exponential Backoff Decorator ---
def retry_with_backoff(retries=3, backoff_in_seconds=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    result = func(*args, **kwargs)
                    if result and result.get('price'):  # Only consider success if price is found
                        return result
                    elif x == retries - 1:
                        logger.warning(f"Failed to fetch valid price from {func.__name__} after {retries} retries.")
                        return result
                    else:
                        raise Exception("Invalid Price Extraction")
                except Exception as e:
                    if x == retries - 1:
                        logger.error(f"{func.__name__} failed permanently: {e}")
                        return {"name": None, "price": None, "rating": None, "details": [], "image_url": None, "error": str(e)}
                    sleep_time = (backoff_in_seconds * 2 ** x)
                    logger.warning(f"{func.__name__} failed: {e}. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    x += 1
        return wrapper
    return decorator

# --- Chrome Options Setup ---
def get_chrome_options():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36")
    return options

def init_driver():
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=get_chrome_options())

# --- Scrapers ---

@retry_with_backoff(retries=3)
def scrape_amazon(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1"
    }

    product_data = { "name": None, "price": None, "rating": None, "details": [], "image_url": None }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        name_elem = soup.select_one("#productTitle")
        if name_elem: product_data["name"] = name_elem.text.strip()

        price_elem = soup.select_one("span.a-price-whole") or soup.select_one("span.a-price .a-offscreen")
        if price_elem:
            price_text = price_elem.text.replace('₹', '').replace(',', '').strip()
            price_match = re.search(r'\d+\.?\d*', price_text)
            if price_match: product_data["price"] = float(price_match.group())

        rating_elem = soup.select_one("span[data-hook='rating-out-of-text']") or soup.select_one("i.a-icon-star span.a-icon-alt")
        product_data["rating"] = rating_elem.text.strip() if rating_elem else "Not Available"

        details_list = soup.select("#feature-bullets ul.a-unordered-list li span.a-list-item")
        product_data["details"] = [item.text.strip() for item in details_list if item.text.strip()]

        img_tag = soup.find("img", {"id": "landingImage"})
        product_data["image_url"] = img_tag.get("src") if img_tag else "Not Available"

        return product_data
    except Exception as e:
        raise e

@retry_with_backoff(retries=2)
def scrape_flipkart(url):
    driver = init_driver()
    product_data = { "name": None, "price": None, "rating": "Not Available", "details": [], "image_url": "Not Available" }
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        name_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span.VU-ZEz")))
        product_data["name"] = name_elem.text.strip()

        price_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.Nx9bqj")))
        price_text = price_elem.text.replace('₹', '').replace(',', '').strip()
        price_match = re.search(r'\d+\.?\d*', price_text)
        if price_match: product_data["price"] = float(price_match.group())

        try:
            rating_elem = driver.find_element(By.CSS_SELECTOR, "div.XQDdHH")
            product_data["rating"] = rating_elem.text.strip()
        except: pass

        try:
            items = driver.find_elements(By.CSS_SELECTOR, "li._7eSDEz")
            product_data["details"] = [item.text.strip() for item in items if item.text.strip()]
        except: pass

        try:
            img_elem = driver.find_element(By.CSS_SELECTOR, "img.DByuf4, img.IZexXJ")
            product_data["image_url"] = img_elem.get_attribute("src")
        except: pass
        
        return product_data
    finally:
        driver.quit()

@retry_with_backoff(retries=2)
def scrape_myntra(url):
    driver = init_driver()
    product_data = { "name": None, "price": None, "rating": "Not Available", "details": [], "image_url": "Not Available" }
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        
        name_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".pdp-name")))
        brand_elem = driver.find_element(By.CSS_SELECTOR, ".pdp-title")
        product_data["name"] = f"{brand_elem.text.strip()} {name_elem.text.strip()}"

        price_elem = driver.find_element(By.CSS_SELECTOR, ".pdp-price strong")
        price_text = price_elem.text.replace('₹', '').replace(',', '').strip()
        price_match = re.search(r'\d+\.?\d*', price_text)
        if price_match: product_data["price"] = float(price_match.group())
        
        try:
            rating_elem = driver.find_element(By.CSS_SELECTOR, ".index-ratingsValue")
            product_data["rating"] = rating_elem.text.strip()
        except: pass

        return product_data
    finally:
        driver.quit()

@retry_with_backoff(retries=2)
def scrape_ajio(url):
    driver = init_driver()
    product_data = { "name": None, "price": None, "rating": "Not Available", "details": [], "image_url": "Not Available" }
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        name_elem = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "prod-name")))
        product_data["name"] = name_elem.text.strip()

        price_elem = driver.find_element(By.CLASS_NAME, "prod-sp")
        price_text = price_elem.text.replace('₹', '').replace(',', '').strip()
        price_match = re.search(r'\d+\.?\d*', price_text)
        if price_match: product_data["price"] = float(price_match.group())

        return product_data
    finally:
        driver.quit()

@retry_with_backoff(retries=2)
def scrape_meesho(url):
    driver = init_driver()
    product_data = { "name": None, "price": None, "rating": "Not Available", "details": [], "image_url": "Not Available" }
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        name_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span.fhfLdV, h1 span")))
        product_data["name"] = name_elem.text.strip()

        price_elem = driver.find_element(By.CSS_SELECTOR, "h4[class*='Price__StyledPrice']")
        price_text = price_elem.text.replace('₹', '').replace(',', '').strip()
        price_match = re.search(r'\d+\.?\d*', price_text)
        if price_match: product_data["price"] = float(price_match.group())

        return product_data
    finally:
        driver.quit()


# --- Unified Dispatcher ---
def scrape_product(url):
    """
    Detects platform from URL, checks cache, routing to platform-specific scraper
    and returns uniform dictionary.
    """
    cached = get_cached_result(url)
    if cached: return cached

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    logger.info(f"Dispatching scraper for domain: {domain}")

    result = None
    if 'amazon' in domain:
        result = scrape_amazon(url)
    elif 'flipkart' in domain:
        result = scrape_flipkart(url)
    elif 'myntra' in domain:
        result = scrape_myntra(url)
    elif 'ajio' in domain:
        result = scrape_ajio(url)
    elif 'meesho' in domain:
        result = scrape_meesho(url)
    else:
        logger.warning(f"Unsupported URL domain provided: {domain}")
        return {"error": "Unsupported platform."}

    if result and not result.get("error"):
        set_cache_result(url, result)

    return result
