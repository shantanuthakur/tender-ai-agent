"""
Template Library manager for official company templates and approved historical documents.
"""
from pathlib import Path
import shutil
import json
from typing import List, Dict, Any, Optional
from config import TEMPLATES_DIR, HISTORICAL_DIR
from database import (
    add_company_document,
    list_company_documents,
    update_company_document_status,
    delete_company_document
)
from parsers.document_extractor import DocumentExtractor

DOCUMENT_CATEGORIES = [
    ("covering_letter", "Bid Covering Letter / Transmittal Letter"),
    ("non_blacklisting", "Non-Blacklisting & Non-Debarment Affidavit / Declaration"),
    ("technical_compliance", "Technical Compliance Sheet / Statement"),
    ("undertaking", "General Tender Acceptance Undertaking / ATC Compliance"),
    ("eligibility_declaration", "Eligibility & Local Content / MII Declaration"),
    ("turnover_certificate", "Annual Financial Turnover Statement / CA Certificate Format"),
    ("past_experience", "Past Experience & Performance Track Record"),
    ("oem_authorization", "OEM Authorization Form (MAF)"),
    ("company_profile", "Comprehensive Company Profile & Credentials"),
    ("boq_commercial", "Commercial / Price Schedule / BOQ"),
    ("other", "Other Tender Annexures & Certifications")
]

class TemplateLibrary:
    """Manages templates and approved historical tender documents."""

    @classmethod
    def categorize_text(cls, text: str, filename: str = "") -> str:
        """Heuristic categorization of document content."""
        search_target = (filename + " " + text[:1500]).lower()

        if any(w in search_target for w in ["cover", "covering letter", "submission of bid", "transmittal"]):
            return "covering_letter"
        if any(w in search_target for w in ["blacklist", "debarment", "not banned", "non-blacklisting", "court of law"]):
            return "non_blacklisting"
        if any(w in search_target for w in ["technical compliance", "parameter", "deviation", "compliance sheet", "specifications compliance"]):
            return "technical_compliance"
        if any(w in search_target for w in ["turnover", "chartered accountant", "financial capacity", "net worth", "fy 20", "balance sheet"]):
            return "turnover_certificate"
        if any(w in search_target for w in ["past experience", "past performance", "client list", "work orders", "purchase order list"]):
            return "past_experience"
        if any(w in search_target for w in ["oem", "manufacturer authorization", "maf", "authorized dealer"]):
            return "oem_authorization"
        if any(w in search_target for w in ["mii", "make in india", "local content", "class-i local", "class-ii local"]):
            return "eligibility_declaration"
        if any(w in search_target for w in ["undertaking", "acceptance of tender", "unconditional acceptance", "atc"]):
            return "undertaking"
        if any(w in search_target for w in ["company profile", "about us", "organization profile", "overview"]):
            return "company_profile"
        if any(w in search_target for w in ["boq", "price bid", "commercial bid", "schedule of rates"]):
            return "boq_commercial"

        return "other"

    @classmethod
    def register_document(cls, file_source_path: Path, is_template: bool, is_approved: bool = True,
                          category_override: Optional[str] = None, title: str = "", description: str = "") -> int:
        """
        Saves a template or historical submission into the library, extracts its text,
        detects layout/structure, and registers it in SQLite.
        """
        dest_dir = TEMPLATES_DIR if is_template else HISTORICAL_DIR
        dest_path = dest_dir / file_source_path.name

        # Ensure no collision overwrite
        counter = 1
        stem = file_source_path.stem
        suffix = file_source_path.suffix
        while dest_path.exists():
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.copy2(file_source_path, dest_path)

        # Extract text and structure
        extracted = DocumentExtractor.extract(dest_path)
        auto_category = cls.categorize_text(extracted.get("text", ""), file_source_path.name)
        chosen_category = category_override or auto_category

        structure_meta = {
            "has_letterhead": extracted.get("detected_styles", {}).get("has_letterhead", False),
            "fonts": extracted.get("detected_styles", {}).get("fonts", []),
            "margins": extracted.get("detected_styles", {}).get("margins", {}),
            "signature_blocks": extracted.get("signature_blocks", []),
            "headings_count": len(extracted.get("headings", [])),
            "tables_count": len(extracted.get("tables", [])),
            "is_template": is_template
        }

        doc_id = add_company_document(
            filename=dest_path.name,
            filepath=str(dest_path.resolve()),
            file_type=extracted.get("file_type", "unknown"),
            category=chosen_category,
            is_approved=1 if is_approved else 0,
            title=title or dest_path.stem.replace("_", " ").title(),
            description=description,
            extracted_text=extracted.get("text", ""),
            structure_metadata=structure_meta
        )
        return doc_id

    @classmethod
    def find_best_template(cls, required_category: str) -> Optional[Dict[str, Any]]:
        """
        Finds the best matching approved template or historical example.
        Hierarchy:
        1. Official Approved Company Template (in TEMPLATES_DIR with is_approved=1)
        2. Approved Historical Submission Document (in HISTORICAL_DIR with is_approved=1)
        3. Returns None if no approved match exists (flags need for user format approval).
        """
        all_docs = list_company_documents(approved_only=True)

        # 1. Search for official approved templates of this category
        for doc in all_docs:
            meta = json.loads(doc.get("structure_metadata") or "{}")
            if doc.get("category") == required_category and meta.get("is_template", False):
                return doc

        # 2. Search for approved historical example of this category
        for doc in all_docs:
            if doc.get("category") == required_category:
                return doc

        # 3. If exact category not found, check if a general undertaking or covering letter template exists
        if required_category in ["undertaking", "eligibility_declaration", "non_blacklisting"]:
            for doc in all_docs:
                meta = json.loads(doc.get("structure_metadata") or "{}")
                if meta.get("is_template", False) and doc.get("category") in ["undertaking", "covering_letter"]:
                    return doc

        return None

    @classmethod
    def get_template_by_id(cls, doc_id: int) -> Optional[Dict[str, Any]]:
        all_docs = list_company_documents()
        for doc in all_docs:
            if doc["id"] == doc_id:
                return doc
        return None
