"""
AI Filter Module
Uses OpenAI GPT to analyze scraped bids and identify which ones
are relevant to Mobile Light Towers (MST), Inflatable Light Systems,
and related portable lighting equipment.
"""

import json
import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# System prompt — highly targeted for MST / inflatable lighting products
SYSTEM_PROMPT = """You are a procurement specialist AI assistant helping a lighting equipment supplier find relevant government tenders on India's GeM (Government e-Marketplace) portal.

The supplier manufactures and supplies the following products:
{product_description}

Your task is to analyze tender/bid listings and determine which are RELEVANT to this supplier.

A bid is RELEVANT if it mentions or relates to ANY of the following:
1. Mobile Lighting Towers (MLT) / Mobile Service Towers (MST)
2. Inflatable Lighting Systems / Balloon Lights / Inflatable Light Towers
3. Portable LED Tower Lights / Floodlight Towers
4. Telescopic Light Masts / Light Mast Systems
5. Mobile Solar Tower Lighting
6. Construction Site Lighting Towers
7. Emergency / Disaster Response Lighting Equipment
8. Outdoor / Industrial Illumination Towers
9. Portable Area Lighting Systems
10. Any equipment where a lighting tower supplier could reasonably bid

RELEVANCE GUIDELINES:
- Be INCLUSIVE — if there's a reasonable chance the bid relates to lighting towers or portable lighting, mark it as relevant
- Consider alternate terminology: "illumination equipment", "portable lights", "field lighting", "area lighting", "tower light", "flood light", etc.
- Government bids may use abbreviated or non-standard terminology — look for contextual clues
- Bids for "light" alone (without tower/portable/inflatable context) are NOT relevant (e.g., "tube light", "ceiling light" are NOT relevant)

IMPORTANT: Respond ONLY with valid JSON. No explanations outside the JSON."""

USER_PROMPT_TEMPLATE = """Analyze these tender/bid listings and determine which are relevant to our lighting tower / inflatable light product line.

For each bid, respond with:
- "index": the bid's position (0-based)
- "relevant": true or false
- "confidence": "high", "medium", or "low"
- "reason": a brief explanation (max 2 sentences) of why it is or isn't relevant
- "matched_product": if relevant, which product category it matches (e.g., "Mobile Light Tower", "Inflatable Light System", "LED Floodlight Tower", etc.)

Respond with a JSON object containing a "results" array:
{{"results": [
  {{"index": 0, "relevant": true, "confidence": "high", "reason": "Bid is for mobile lighting towers for construction site", "matched_product": "Mobile Light Tower"}},
  {{"index": 1, "relevant": false, "confidence": "high", "reason": "Bid is for office ceiling LED panel lights, not portable/tower lighting", "matched_product": null}}
]}}

Here are the bids to analyze:

{bids_text}"""


def filter_relevant_bids(
    bids: list[dict],
    product_keywords: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    batch_size: int = 25,
) -> list[dict]:
    """
    Use OpenAI GPT to filter bids for relevance to MST / inflatable lighting products.

    Args:
        bids: List of bid dictionaries from the scraper.
        product_keywords: Comma-separated product keywords.
        api_key: OpenAI API key.
        model: OpenAI model to use (gpt-4o-mini is cost-effective).
        batch_size: Number of bids to process per API call.

    Returns:
        List of relevant bid dictionaries with added AI analysis fields.
    """
    if not bids:
        logger.info("No bids to filter.")
        return []

    client = OpenAI(api_key=api_key)
    relevant_bids = []

    # Build product description from keywords
    product_desc = f"""
    - Mobile Lighting Tower Systems (MLT / MST)
    - Inflatable Lighting Tower Systems / Balloon Lights
    - Portable LED Tower Lights / Floodlight Towers
    - Telescopic Light Masts / Light Mast Systems
    - Mobile Solar Tower Lighting
    - Emergency / Disaster Lighting Equipment
    - Additional keywords: {product_keywords}
    """

    system_prompt = SYSTEM_PROMPT.format(product_description=product_desc)

    # Process bids in batches
    total_batches = (len(bids) + batch_size - 1) // batch_size
    logger.info(f"🧠 Filtering {len(bids)} bids using AI model '{model}' ({total_batches} batch{'es' if total_batches > 1 else ''})...")

    for batch_idx in range(0, len(bids), batch_size):
        batch = bids[batch_idx : batch_idx + batch_size]
        batch_num = (batch_idx // batch_size) + 1
        logger.info(f"   Processing batch {batch_num}/{total_batches} ({len(batch)} bids)...")

        # Format bids for the prompt
        bids_text = _format_bids_for_prompt(batch)
        user_prompt = USER_PROMPT_TEMPLATE.format(bids_text=bids_text)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # Low temperature for consistent classification
                response_format={"type": "json_object"},
                max_tokens=4000,
            )

            result_text = response.choices[0].message.content.strip()
            analysis = _parse_ai_response(result_text)

            if analysis:
                relevant_count = 0
                for item in analysis:
                    idx = item.get("index", -1)
                    is_relevant = item.get("relevant", False)

                    if is_relevant and 0 <= idx < len(batch):
                        bid = batch[idx].copy()
                        bid["ai_confidence"] = item.get("confidence", "unknown")
                        bid["ai_reason"] = item.get("reason", "Marked as relevant by AI")
                        bid["matched_product"] = item.get("matched_product", "")
                        relevant_bids.append(bid)
                        relevant_count += 1

                logger.info(f"   ✅ Found {relevant_count} relevant bids in batch {batch_num}")
            else:
                logger.warning(f"   ⚠️ Could not parse AI response for batch {batch_num}, using keyword fallback")
                relevant_bids.extend(_keyword_fallback(batch, product_keywords))

        except Exception as e:
            logger.error(f"   ❌ AI filter error for batch {batch_num}: {e}")
            # On error, fall back to keyword matching
            relevant_bids.extend(_keyword_fallback(batch, product_keywords))

    logger.info(
        f"🎯 AI filtering complete. {len(relevant_bids)} relevant bids found out of {len(bids)} total."
    )
    return relevant_bids


def _format_bids_for_prompt(bids: list[dict]) -> str:
    """Format a list of bids into a readable text for the AI prompt."""
    lines = []
    for i, bid in enumerate(bids):
        title = bid.get("title", "N/A")
        bid_number = bid.get("bid_number", "N/A")
        department = bid.get("department", "N/A")
        items = bid.get("items", "")
        quantity = bid.get("quantity", "")
        full_desc = bid.get("full_description", "")

        entry = f"[{i}] Bid: {bid_number}\n    Title: {title}"
        if items and items != title:
            entry += f"\n    Items: {items}"
        if full_desc and full_desc != title:
            entry += f"\n    Description: {full_desc[:300]}"
        if department:
            entry += f"\n    Department: {department}"
        if quantity:
            entry += f"\n    Quantity: {quantity}"

        lines.append(entry)

    return "\n\n".join(lines)


def _parse_ai_response(response_text: str) -> Optional[list[dict]]:
    """Parse the AI's JSON response into a list of analysis results."""
    try:
        result = json.loads(response_text)

        # Handle both direct array and wrapped object formats
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # Look for an array in the response object
            for key in ["results", "bids", "analysis", "data", "items", "tenders"]:
                if key in result and isinstance(result[key], list):
                    return result[key]
            # If it's a single result wrapped in an object
            if "index" in result:
                return [result]

        return None

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI response as JSON: {e}")
        logger.debug(f"Raw response: {response_text[:500]}")

        # Try to extract JSON from the response text
        try:
            # Sometimes the response has markdown fences
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                return _parse_ai_response(json_str)
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                return _parse_ai_response(json_str)
        except Exception:
            pass

        return None


def _keyword_fallback(bids: list[dict], keywords_str: str) -> list[dict]:
    """Keyword-based fallback filtering when AI is unavailable."""
    relevant = []
    for bid in bids:
        bid_text = " ".join([
            bid.get("title", ""),
            bid.get("items", ""),
            bid.get("full_description", ""),
        ]).lower()

        if _keyword_match(bid_text, keywords_str):
            bid_copy = bid.copy()
            bid_copy["ai_confidence"] = "fallback"
            bid_copy["ai_reason"] = "Matched by keyword (AI unavailable)"
            bid_copy["matched_product"] = "Keyword Match"
            relevant.append(bid_copy)

    return relevant


def _keyword_match(text: str, keywords_str: str) -> bool:
    """Check if text matches any of the product-related keywords."""
    text_lower = text.lower()
    keywords = [kw.strip().lower() for kw in keywords_str.split(",")]

    for keyword in keywords:
        if keyword and keyword in text_lower:
            return True

    # Also check specific lighting tower terms
    lighting_terms = [
        "lighting tower",
        "light tower",
        "tower light",
        "inflatable light",
        "balloon light",
        "portable light tower",
        "flood light tower",
        "floodlight tower",
        "light mast",
        "mast light",
        "illumination tower",
        "led tower",
        "mobile light",
        "mobile lighting",
        "mobile service tower",
        "solar tower light",
        "area lighting",
        "portable illumination",
        "inflatable lighting",
    ]
    for term in lighting_terms:
        if term in text_lower:
            return True

    # Check abbreviation patterns
    abbreviations = ["mst", "mlt", "ilt"]
    words = text_lower.split()
    for abbr in abbreviations:
        if abbr in words:
            return True

    return False
