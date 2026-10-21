"""
Style analyzer: extracts company writing patterns, signature blocks, and corporate tone.
"""
from typing import Dict, Any, List
import json
import re
from database import list_company_documents

class StyleAnalyzer:
    """Analyzes approved company documents to establish styling rules."""

    @classmethod
    def synthesize_style_profile(cls) -> Dict[str, Any]:
        """Synthesizes writing style, standard phrasing, fonts, and signature blocks."""
        approved_docs = list_company_documents(approved_only=True)

        all_fonts = set()
        signature_blocks = []
        common_phrases = set()
        letterhead_detected = False

        standard_keywords = [
            "we hereby confirm", "we solemnly declare", "unconditional acceptance",
            "in accordance with the terms", "with reference to the tender",
            "for and on behalf of", "authorized signatory", "seal of the company"
        ]

        for doc in approved_docs:
            text = doc.get("extracted_text", "")
            meta = json.loads(doc.get("structure_metadata") or "{}")

            if meta.get("has_letterhead"):
                letterhead_detected = True

            for font in meta.get("fonts", []):
                all_fonts.add(font)

            for sig in meta.get("signature_blocks", []):
                if sig not in signature_blocks:
                    signature_blocks.append(sig)

            lower_text = text.lower()
            for phrase in standard_keywords:
                if phrase in lower_text:
                    common_phrases.add(phrase)

        primary_font = list(all_fonts)[0] if all_fonts else "Calibri"

        default_signature = (
            "For and on behalf of [Company Name]\n\n"
            "_____________________________________\n"
            "(Authorized Signatory)\n"
            "Name: [Authorized Signatory Name]\n"
            "Designation: [Authorized Signatory Designation]\n"
            "Date: [Current Date]\n"
            "Place: [City]\n"
            "[Company Seal / Stamp]"
        )

        chosen_sig = signature_blocks[0] if signature_blocks else default_signature

        return {
            "primary_font": primary_font,
            "detected_fonts": list(all_fonts),
            "letterhead_detected": letterhead_detected,
            "signature_block_style": chosen_sig,
            "recurring_formal_phrases": list(common_phrases),
            "doc_count_analyzed": len(approved_docs),
            "summary": (
                f"Company profile derived from {len(approved_docs)} approved document(s). "
                f"Primary font: {primary_font}. "
                f"Letterhead present: {'Yes' if letterhead_detected else 'Not detected'}. "
                f"Uses formal, statutory tender phrasing conforming to GeM & public procurement norms."
            )
        }
