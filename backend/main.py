"""
GeM Tender AI Agent — Main Entry Point
========================================
Scrapes tenders from bidplus.gem.gov.in, uses OpenAI to identify
Mobile Light Tower (MST) and Inflatable Light System tenders,
and saves results as Excel, Word, and JSON documents.

Usage:
    python main.py
    python main.py --pages 5 --headless true
    python main.py --keywords "light tower,MST,inflatable light"
"""

import os
import sys
import argparse
import logging
from datetime import datetime

from dotenv import load_dotenv

# ─── Configure logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ─── Load environment variables ─────────────────────────────────────
load_dotenv()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GeM Tender AI Agent — Find Mobile Light Tower & Inflatable Light System tenders"
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=int(os.getenv("MAX_PAGES", "5")),
        help="Maximum pages to scrape per keyword (default: 5)",
    )
    parser.add_argument(
        "--headless",
        type=str,
        default=os.getenv("HEADLESS", "true"),
        help="Run browser in headless mode: true/false (default: true)",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default=os.getenv("SEARCH_KEYWORDS", ""),
        help="Comma-separated search keywords for GeM search",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("AI_MODEL", "gpt-4o-mini"),
        help="OpenAI model to use (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Skip keyword search and scrape all bids instead",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Skip fetching individual bid detail pages",
    )
    return parser.parse_args()


def main():
    """Run the full tender scraping + AI filtering + saving pipeline."""
    args = parse_args()

    headless = args.headless.lower() in ("true", "1", "yes")
    api_key = os.getenv("OPENAI_API_KEY", "")
    product_keywords = os.getenv("PRODUCT_KEYWORDS", "mobile lighting tower,inflatable lighting tower,MST lighting")

    # ─── Validate API key ───────────────────────────────────────
    if not api_key or api_key == "your-openai-api-key-here":
        logger.error("❌ OPENAI_API_KEY is not set! Please add your API key to .env")
        logger.error("   Edit backend/.env and replace 'your-openai-api-key-here' with your actual key")
        sys.exit(1)

    # ─── Print banner ───────────────────────────────────────────
    print()
    print("=" * 65)
    print("  GeM Tender AI Agent")
    print("  Mobile Light Tower & Inflatable Light System Finder")
    print("=" * 65)
    print(f"  Started:   {datetime.now().strftime('%d %b %Y, %I:%M:%S %p')}")
    print(f"  Mode:      {'Keyword Search' if not args.no_search else 'All Bids'}")
    print(f"  Max Pages: {args.pages}")
    print(f"  Headless:  {headless}")
    print(f"  AI Model:  {args.model}")
    print("=" * 65)
    print()

    # ─── Import modules (after env is loaded) ───────────────────
    from scraper import search_gem_bids, scrape_gem_bids, scrape_bid_details
    from ai_filter import filter_relevant_bids
    from save_results import (
        load_seen_bids,
        filter_new_bids,
        save_all,
    )

    # ─── STEP 1: Scrape bids from GeM ──────────────────────────
    logger.info("━" * 50)
    logger.info("STEP 1: Scraping bids from GeM portal...")
    logger.info("━" * 50)

    if not args.no_search:
        # Search-first strategy: use keywords to find relevant bids
        keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
        if not keywords:
            keywords = [
                "mobile light tower",
                "inflatable light",
                "MST light",
                "lighting tower",
                "balloon light",
                "portable light tower",
                "LED tower light",
            ]
        logger.info(f"🔍 Search keywords: {keywords}")
        all_bids = search_gem_bids(
            keywords=keywords, max_pages=args.pages, headless=headless
        )
    else:
        # Fallback: scrape all bids (noisier but works if search fails)
        all_bids = scrape_gem_bids(max_pages=args.pages, headless=headless)

    if not all_bids:
        logger.warning("⚠️ No bids scraped from GeM. This may be due to:")
        logger.warning("   - Website blocking automated access")
        logger.warning("   - Network connectivity issues")
        logger.warning("   - Page structure changes on GeM")
        logger.warning("   Try running with --headless false to see the browser")
        print()
        print("=" * 65)
        print("  ❌ No bids were scraped. Please check the logs above.")
        print("=" * 65)
        return

    logger.info(f"📊 Total bids scraped: {len(all_bids)}")

    # ─── STEP 1.5: Filter out already-seen bids ────────────────
    seen_bids = load_seen_bids()
    new_bids = filter_new_bids(all_bids, seen_bids)

    if not new_bids:
        logger.info("✅ No new bids to process (all have been seen before)")
        print()
        print("=" * 65)
        print("  ℹ️  No new bids found. All scraped bids were already processed.")
        print("=" * 65)
        return

    # ─── STEP 2: Enrich with bid details (optional) ────────────
    if not args.no_details and len(new_bids) <= 50:
        logger.info("━" * 50)
        logger.info("STEP 2: Fetching bid details...")
        logger.info("━" * 50)
        new_bids = scrape_bid_details(
            new_bids, headless=headless, max_detail_pages=30
        )
    else:
        logger.info("STEP 2: Skipping bid detail fetching (--no-details or too many bids)")

    # ─── STEP 3: AI filter ─────────────────────────────────────
    logger.info("━" * 50)
    logger.info("STEP 3: AI filtering for lighting tower relevance...")
    logger.info("━" * 50)

    relevant_bids = filter_relevant_bids(
        bids=new_bids,
        product_keywords=product_keywords,
        api_key=api_key,
        model=args.model,
    )

    if not relevant_bids:
        logger.info("ℹ️ No relevant tenders found in this batch.")
        print()
        print("=" * 65)
        print("  ℹ️  No relevant tenders found for Mobile Light Tower / MST /")
        print("      Inflatable Light Systems in the current batch.")
        print("=" * 65)
        # Still update the seen log so we don't re-process these bids
        from save_results import update_seen_log
        update_seen_log(new_bids)
        return

    # ─── STEP 4: Save results ──────────────────────────────────
    logger.info("━" * 50)
    logger.info("STEP 4: Saving results...")
    logger.info("━" * 50)

    saved_files = save_all(relevant_bids)

    # ─── DONE: Print summary ───────────────────────────────────
    print()
    print("=" * 65)
    print("  ✅ TENDER SEARCH COMPLETE")
    print("=" * 65)
    print()
    print(f"  📊 Bids Scraped:        {len(all_bids)}")
    print(f"  🆕 New Bids:            {len(new_bids)}")
    print(f"  🎯 Relevant Tenders:    {len(relevant_bids)}")
    print()

    # Confidence breakdown
    high = sum(1 for b in relevant_bids if b.get("ai_confidence") == "high")
    medium = sum(1 for b in relevant_bids if b.get("ai_confidence") == "medium")
    low = sum(1 for b in relevant_bids if b.get("ai_confidence") == "low")
    fallback = sum(1 for b in relevant_bids if b.get("ai_confidence") == "fallback")

    print(f"  Confidence Breakdown:")
    print(f"    🟢 High:     {high}")
    print(f"    🟡 Medium:   {medium}")
    print(f"    🔴 Low:      {low}")
    if fallback:
        print(f"    ⚪ Fallback:  {fallback}")
    print()

    # File paths
    print("  📁 Output Files:")
    print(f"    📄 Excel: {saved_files['excel']}")
    print(f"    📝 Word:  {saved_files['word']}")
    print(f"    🔗 JSON:  {saved_files['json']}")
    print()

    # Show top relevant tenders
    print("  📋 Top Relevant Tenders:")
    print("  " + "-" * 63)
    for i, bid in enumerate(relevant_bids[:10], 1):
        conf = bid.get("ai_confidence", "?")
        conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
        bid_num = bid.get("bid_number", "N/A")
        title = bid.get("title", "N/A")[:50]
        matched = bid.get("matched_product", "")
        print(f"  {conf_icon} {i}. [{bid_num}]")
        print(f"       {title}")
        if matched:
            print(f"       Product: {matched}")
        print()

    print("=" * 65)
    print("  Open the Excel or Word file to view full details.")
    print("  Or open frontend/index.html for the web dashboard.")
    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
