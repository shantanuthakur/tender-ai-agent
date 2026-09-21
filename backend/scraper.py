"""
GeM Bid Scraper Module
Scrapes tender/bid listings from bidplus.gem.gov.in/all-bids
using undetected-chromedriver to bypass anti-bot protections.

Strategy: Search-first approach — uses GeM's search box to find
lighting-related bids directly, reducing noise significantly.
"""

import time
import random
import logging
import re
import json
from typing import Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

GEM_ALL_BIDS_URL = "https://bidplus.gem.gov.in/all-bids"
GEM_BID_DETAIL_URL = "https://bidplus.gem.gov.in/showbidDocument/"


def _random_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Sleep for a random duration to mimic human behavior."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def _create_driver(headless: bool = True) -> uc.Chrome:
    """Create and configure an undetected Chrome driver."""
    options = uc.ChromeOptions()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def _wait_for_bids_loaded(driver: uc.Chrome, timeout: int = 30):
    """Wait for bid content to load on the page."""
    try:
        # GeM uses #bidCard as the primary bids container, with #searchBid for the search input
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#bidCard, #searchBid, .card, #pagi_content")
            )
        )
        # Additional wait for dynamic AJAX rendering
        _random_delay(1.5, 3)

        # Wait until bid cards appear inside #bidCard
        try:
            WebDriverWait(driver, 12).until(
                lambda d: len(
                    d.find_elements(
                        By.CSS_SELECTOR,
                        "#bidCard .card, #bidCard > div, .card, #pagi_content > div",
                    )
                )
                > 0
            )
        except TimeoutException:
            logger.debug("No bid card divs found inside container within 12s")

        return True
    except TimeoutException:
        logger.warning("⚠️ Timeout waiting for bids container to load")
        return False


def _parse_bid_cards(page_source: str) -> list[dict]:
    """
    Parse bid card elements from the page HTML.
    Each bid card on GeM typically contains:
    - Bid number (GEM/YYYY/B/XXXXXXX)
    - Title/description
    - Department
    - Quantity
    - Start date, end date
    - Bid value
    - Link to detail page
    """
    soup = BeautifulSoup(page_source, "html.parser")
    bids = []

    # Strategy 1: GeM uses div#bidCard with child elements having class 'card'
    bid_containers = soup.select("div#bidCard div.card")
    if not bid_containers:
        bid_containers = soup.select("div#bidCard > div")
    if not bid_containers:
        bid_containers = soup.select("div.card")
    if not bid_containers:
        bid_containers = soup.select("div#pagi_content div.border")
    if not bid_containers:
        bid_containers = soup.select("div#pagi_content > div")
    if not bid_containers:
        bid_containers = soup.find_all(
            "div", class_=lambda c: c and "border" in c
        )

    for container in bid_containers:
        try:
            bid = _extract_bid_data(container)
            if bid and bid.get("bid_number"):
                bids.append(bid)
        except Exception as e:
            logger.debug(f"Failed to parse a bid card: {e}")
            continue

    # Strategy 2: If no structured containers found, try text-based extraction
    if not bids:
        bids = _extract_bids_from_text(soup)

    return bids


def _extract_bid_data(container) -> Optional[dict]:
    """Extract bid data from a single bid card container."""
    bid = {
        "bid_number": "",
        "title": "",
        "department": "",
        "quantity": "",
        "start_date": "",
        "end_date": "",
        "bid_value": "",
        "detail_link": "",
        "items": "",
    }

    # Extract all text content and links
    all_text = container.get_text(separator="\n", strip=True)
    all_links = container.find_all("a", href=True)

    # Robust bid number extraction using regex
    match = re.search(r"(GEM/\d{4}/[A-Z]/\d+)", all_text)
    if match:
        bid["bid_number"] = match.group(1)

    # Find detail link — links containing "showbidDocument", "showradocumentPdf", etc.
    for link in all_links:
        href = link.get("href", "")
        if (
            "showbidDocument" in href
            or "showradocumentPdf" in href
            or "showdirectradocumentPdf" in href
            or "showbid" in href.lower()
        ):
            if not href.startswith("http"):
                href = f"https://bidplus.gem.gov.in/{href.lstrip('/')}"
            bid["detail_link"] = href

            # Check if link text has bid number
            link_text = link.get_text(strip=True)
            if not bid["bid_number"]:
                m = re.search(r"(GEM/\d{4}/[A-Z]/\d+)", link_text)
                if m:
                    bid["bid_number"] = m.group(1)
            break

    # Extract fields by label patterns
    lines = all_text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.strip().lower()

        if any(
            kw in line_lower
            for kw in ["items:", "item description:", "product:", "items"]
        ):
            value = _get_next_value(lines, i)
            if value:
                bid["title"] = value
                bid["items"] = value

        elif any(
            kw in line_lower
            for kw in [
                "department name and address:",
                "department name",
                "department:",
                "ministry:",
                "organisation:",
            ]
        ):
            value = _get_next_value(lines, i)
            if value:
                bid["department"] = value

        elif "quantity:" in line_lower or "quantity" in line_lower:
            value = _get_next_value(lines, i)
            if value:
                bid["quantity"] = value

        elif "start date:" in line_lower or "start date" in line_lower:
            value = _get_next_value(lines, i)
            if value:
                bid["start_date"] = value

        elif any(
            kw in line_lower
            for kw in ["end date:", "closing date:", "end date"]
        ):
            value = _get_next_value(lines, i)
            if value:
                bid["end_date"] = value

        elif any(
            kw in line_lower
            for kw in ["estimated value:", "bid value:", "total value:"]
        ):
            value = _get_next_value(lines, i)
            if value:
                bid["bid_value"] = value

    # If title is still empty, try to get the first meaningful text
    if not bid["title"]:
        for line in lines:
            line = line.strip()
            if (
                len(line) > 15
                and not line.startswith("GEM/")
                and not line.startswith("Bid No")
                and not line.startswith("RA NO")
                and "date" not in line.lower()
            ):
                bid["title"] = line
                break

    # Build detail link from bid number if not found
    if not bid["detail_link"] and bid["bid_number"]:
        bid_id = bid["bid_number"].replace("/", "_")
        bid["detail_link"] = f"{GEM_BID_DETAIL_URL}{bid_id}"

    return bid



def _get_next_value(lines: list, current_index: int) -> str:
    """Get the next non-empty, non-label line after current index."""
    # First check if the value is on the same line after a colon
    current_line = lines[current_index].strip()
    if ":" in current_line:
        value = current_line.split(":", 1)[1].strip()
        if value:
            return value

    # Otherwise look at subsequent lines
    for j in range(current_index + 1, min(current_index + 3, len(lines))):
        value = lines[j].strip()
        if value and len(value) > 1:
            return value
    return ""


def _extract_bids_from_text(soup) -> list[dict]:
    """
    Fallback: Extract bid data by searching all text for GEM/ patterns
    and building bid records from surrounding context.
    """
    bids = []
    body_text = soup.get_text(separator="\n", strip=True)
    lines = body_text.split("\n")

    current_bid = None
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # New bid starts with a GEM/ number
        if line.startswith("GEM/"):
            if current_bid and current_bid.get("bid_number"):
                bids.append(current_bid)
            current_bid = {
                "bid_number": line,
                "title": "",
                "department": "",
                "quantity": "",
                "start_date": "",
                "end_date": "",
                "bid_value": "",
                "detail_link": f"{GEM_BID_DETAIL_URL}{line.replace('/', '_')}",
                "items": "",
            }
        elif current_bid:
            line_lower = line.lower()
            if not current_bid["title"] and len(line) > 15:
                current_bid["title"] = line
                current_bid["items"] = line

    # Don't forget the last bid
    if current_bid and current_bid.get("bid_number"):
        bids.append(current_bid)

    # Also find links for bid detail pages
    all_links = soup.find_all("a", href=True)
    link_map = {}
    for link in all_links:
        href = link.get("href", "")
        text = link.get_text(strip=True)
        if text.startswith("GEM/"):
            if not href.startswith("http"):
                href = f"https://bidplus.gem.gov.in{href}"
            link_map[text] = href

    for bid in bids:
        if bid["bid_number"] in link_map:
            bid["detail_link"] = link_map[bid["bid_number"]]

    return bids


def _go_to_next_page(driver: uc.Chrome, current_page: int) -> bool:
    """
    Navigate to the next page of bid listings.
    Returns True if successful, False if no next page exists.
    """
    try:
        next_page_num = current_page + 1

        # Strategy 1: Look for light-pagination or standard pagination links with next page number
        try:
            pagination_links = driver.find_elements(
                By.CSS_SELECTOR,
                "#light-pagination a, #light-pagination li a, ul.pagination li a, .pagination2 a",
            )
            for link in pagination_links:
                link_text = link.text.strip()
                if link_text == str(next_page_num):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                    _random_delay(0.5, 1)
                    driver.execute_script("arguments[0].click();", link)
                    _random_delay(1.5, 3)
                    _wait_for_bids_loaded(driver, timeout=20)
                    return True
        except (NoSuchElementException, StaleElementReferenceException):
            pass

        # Strategy 2: Look for a "Next" or "»" button
        try:
            next_buttons = driver.find_elements(
                By.CSS_SELECTOR,
                "#light-pagination a.next, #light-pagination li a, ul.pagination li a, .pagination2 a",
            )
            for btn in next_buttons:
                btn_text = btn.text.strip().lower()
                if btn_text in ["next", "»", "›", "next »"]:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    _random_delay(0.5, 1)
                    driver.execute_script("arguments[0].click();", btn)
                    _random_delay(1.5, 3)
                    _wait_for_bids_loaded(driver, timeout=20)
                    return True
        except (NoSuchElementException, StaleElementReferenceException):
            pass

        # Strategy 3: Try invoking GeM's loadBids JavaScript function directly
        try:
            driver.execute_script(f"if (typeof loadBids === 'function') {{ loadBids({next_page_num}); }}")
            _random_delay(2, 3.5)
            return _wait_for_bids_loaded(driver, timeout=20)
        except Exception:
            pass

        return False

    except Exception as e:
        logger.warning(f"⚠️ Failed to navigate to next page: {e}")
        return False


def _perform_search(driver: uc.Chrome, keyword: str) -> bool:
    """
    Use GeM's search box (#searchBid) and button (#searchBidRA) to search for a specific keyword.
    Returns True if search was successfully performed.
    """
    try:
        # GeM uses #searchBid specifically for the tender bids search input
        search_selectors = [
            "#searchBid",
            "input[name='searchBid']",
            "input[placeholder*='Enter Keyword' i]",
            "input[placeholder*='Keyword' i]",
        ]

        search_input = None
        for selector in search_selectors:
            try:
                search_input = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if search_input and search_input.is_displayed():
                    break
            except (TimeoutException, NoSuchElementException):
                continue

        if not search_input:
            logger.warning(f"   Could not find search box for keyword '{keyword}'")
            return False

        # Scroll into view and focus
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_input)
        _random_delay(0.4, 0.8)

        # Clear previous search via JS and Selenium
        try:
            search_input.click()
        except Exception:
            driver.execute_script("arguments[0].focus();", search_input)

        driver.execute_script("arguments[0].value = '';", search_input)
        search_input.clear()
        _random_delay(0.2, 0.4)

        # Type keyword character by character
        for char in keyword:
            search_input.send_keys(char)
            time.sleep(random.uniform(0.03, 0.08))

        # Ensure value is also set in DOM and trigger input change event
        driver.execute_script(
            """
            var el = arguments[0];
            el.value = arguments[1];
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            search_input,
            keyword,
        )
        _random_delay(0.5, 1.0)

        # Click the search button (#searchBidRA)
        search_btn = None
        for btn_sel in ["#searchBidRA", "button.search_btn", "button[type='button'].search_btn"]:
            try:
                search_btn = driver.find_element(By.CSS_SELECTOR, btn_sel)
                if search_btn:
                    break
            except NoSuchElementException:
                continue

        if search_btn:
            driver.execute_script("arguments[0].click();", search_btn)
        else:
            # Fallback: Trigger GeM's searchBidRA click event or call loadBids(1)
            driver.execute_script(
                """
                if (typeof window.param !== 'undefined') {
                    window.param['searchBid'] = arguments[0];
                    window.currentPage = 1;
                    if (typeof loadBids === 'function') { loadBids(1); }
                }
                """,
                keyword,
            )

        _random_delay(2.5, 4.0)

        # Wait for results to load in #bidCard
        _wait_for_bids_loaded(driver, timeout=20)
        return True

    except Exception as e:
        logger.warning(f"   Search for '{keyword}' failed: {e}")
        return False


def scrape_gem_bids(max_pages: int = 5, headless: bool = True) -> list[dict]:
    """
    Scrape all bids from GeM bid listing (no keyword filter).
    Good as a fallback when search doesn't work.

    Args:
        max_pages: Maximum number of pages to scrape.
        headless: Run browser in headless mode.

    Returns:
        List of bid dictionaries.
    """
    all_bids = []
    driver = None

    try:
        logger.info("🚀 Starting GeM bid scraper (all bids mode)...")
        driver = _create_driver(headless=headless)

        logger.info(f"📄 Loading GeM bids page: {GEM_ALL_BIDS_URL}")
        driver.get(GEM_ALL_BIDS_URL)

        if not _wait_for_bids_loaded(driver):
            logger.warning("⚠️ Page content may not be fully loaded, proceeding anyway...")

        for page_num in range(1, max_pages + 1):
            logger.info(f"📑 Scraping page {page_num}/{max_pages}...")

            page_bids = _parse_bid_cards(driver.page_source)
            logger.info(f"   Found {len(page_bids)} bids on page {page_num}")

            if not page_bids:
                logger.info("   Trying alternative parsing...")
                soup = BeautifulSoup(driver.page_source, "html.parser")
                page_bids = _extract_bids_from_text(soup)
                logger.info(f"   Alternative parsing found {len(page_bids)} bids")

            all_bids.extend(page_bids)

            if page_num < max_pages:
                if not _go_to_next_page(driver, page_num):
                    logger.info(f"   No more pages available after page {page_num}")
                    break
                _random_delay(2, 4)

    except WebDriverException as e:
        logger.error(f"❌ Browser error: {e}")
    except Exception as e:
        logger.error(f"❌ Scraper error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    unique_bids = _deduplicate_bids(all_bids)
    logger.info(f"✅ Scraping complete. Total unique bids: {len(unique_bids)}")
    return unique_bids


def search_gem_bids(
    keywords: list[str], max_pages: int = 3, headless: bool = True
) -> list[dict]:
    """
    Search GeM bids using specific keywords related to lighting products.
    This is the PRIMARY scraping strategy — search first, then scrape results.

    Args:
        keywords: List of search keywords (e.g., ["light tower", "MST", "inflatable light"]).
        max_pages: Max pages to scrape per keyword search.
        headless: Run in headless mode.

    Returns:
        Combined list of bids from all keyword searches.
    """
    all_bids = []
    driver = None

    try:
        logger.info(f"🔍 Starting GeM keyword search with {len(keywords)} keywords...")
        driver = _create_driver(headless=headless)

        for kw_idx, keyword in enumerate(keywords, 1):
            logger.info(f"🔍 [{kw_idx}/{len(keywords)}] Searching GeM for: '{keyword}'")

            try:
                # Navigate to bids page if not already loaded
                if kw_idx == 1 or "all-bids" not in driver.current_url:
                    driver.get(GEM_ALL_BIDS_URL)
                    _random_delay(3, 5)
                    _wait_for_bids_loaded(driver, timeout=25)

                # Perform the search
                search_ok = _perform_search(driver, keyword)
                if not search_ok:
                    logger.warning(f"   Retrying search with fresh page load for '{keyword}'...")
                    driver.get(GEM_ALL_BIDS_URL)
                    _random_delay(3, 5)
                    _wait_for_bids_loaded(driver, timeout=20)
                    search_ok = _perform_search(driver, keyword)

                # Scrape results pages
                for page_num in range(1, max_pages + 1):
                    page_bids = _parse_bid_cards(driver.page_source)
                    if not page_bids:
                        soup = BeautifulSoup(driver.page_source, "html.parser")
                        page_bids = _extract_bids_from_text(soup)

                    # Tag each bid with the search keyword used
                    for bid in page_bids:
                        bid["search_keyword"] = keyword

                    all_bids.extend(page_bids)
                    logger.info(
                        f"   Page {page_num}: found {len(page_bids)} bids for '{keyword}'"
                    )

                    if not page_bids:
                        logger.info(f"   No bids found on page {page_num}, stopping pagination")
                        break

                    if page_num < max_pages:
                        if not _go_to_next_page(driver, page_num):
                            break
                        _random_delay(2, 4)

            except Exception as e:
                logger.warning(f"⚠️ Search for '{keyword}' failed: {e}")
                continue

            # Small delay between keyword searches
            if kw_idx < len(keywords):
                _random_delay(2, 4)

    except Exception as e:
        logger.error(f"❌ Search scraper error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    unique_bids = _deduplicate_bids(all_bids)
    logger.info(f"✅ Keyword search complete. Total unique bids: {len(unique_bids)}")
    return unique_bids


def scrape_bid_details(
    bids: list[dict], headless: bool = True, max_detail_pages: int = 20
) -> list[dict]:
    """
    Visit individual bid detail pages to enrich bid data with
    full descriptions, specifications, and additional metadata.

    Args:
        bids: List of bids with detail_link populated.
        headless: Run in headless mode.
        max_detail_pages: Max number of detail pages to visit (to limit time).

    Returns:
        Enriched list of bids.
    """
    if not bids:
        return bids

    driver = None
    enriched = []
    to_visit = [b for b in bids if b.get("detail_link")][:max_detail_pages]

    if not to_visit:
        return bids

    logger.info(f"🔎 Fetching details for {len(to_visit)} bids...")

    try:
        driver = _create_driver(headless=headless)

        for i, bid in enumerate(to_visit, 1):
            try:
                link = bid["detail_link"]
                logger.info(f"   [{i}/{len(to_visit)}] Visiting {bid.get('bid_number', 'unknown')}...")

                driver.get(link)
                _random_delay(2, 4)

                # Parse the detail page
                soup = BeautifulSoup(driver.page_source, "html.parser")
                detail_text = soup.get_text(separator="\n", strip=True)

                # Extract additional fields from detail page
                enriched_bid = bid.copy()
                enriched_bid["full_description"] = _extract_detail_field(
                    detail_text, ["description", "item description", "product description"]
                )
                enriched_bid["specifications"] = _extract_detail_field(
                    detail_text, ["specification", "technical specification"]
                )
                enriched_bid["delivery_location"] = _extract_detail_field(
                    detail_text, ["delivery", "consignee", "location"]
                )

                # If we found a better title from detail page, update it
                if enriched_bid["full_description"] and not enriched_bid.get("title"):
                    enriched_bid["title"] = enriched_bid["full_description"][:200]

                enriched.append(enriched_bid)

            except Exception as e:
                logger.debug(f"   Failed to fetch detail for {bid.get('bid_number')}: {e}")
                enriched.append(bid)

    except Exception as e:
        logger.error(f"❌ Detail scraper error: {e}")
        # Return original bids if detail scraping fails completely
        return bids
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    # Add back any bids we didn't visit
    visited_numbers = {b.get("bid_number") for b in enriched}
    for bid in bids:
        if bid.get("bid_number") not in visited_numbers:
            enriched.append(bid)

    logger.info(f"✅ Detail enrichment complete for {len(to_visit)} bids")
    return enriched


def _extract_detail_field(text: str, field_labels: list[str]) -> str:
    """Extract a field value from a detail page's text content."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.strip().lower()
        for label in field_labels:
            if label in line_lower:
                # Check same line after colon
                if ":" in line:
                    value = line.split(":", 1)[1].strip()
                    if value:
                        return value
                # Check next lines
                for j in range(i + 1, min(i + 5, len(lines))):
                    val = lines[j].strip()
                    if val and len(val) > 3:
                        return val
    return ""


def _deduplicate_bids(bids: list[dict]) -> list[dict]:
    """Remove duplicate bids by bid_number."""
    seen = set()
    unique = []
    for bid in bids:
        bid_num = bid.get("bid_number", "")
        if bid_num and bid_num not in seen:
            seen.add(bid_num)
            unique.append(bid)
        elif not bid_num:
            unique.append(bid)
    return unique
