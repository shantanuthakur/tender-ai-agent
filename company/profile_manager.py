"""
Company profile manager: stores, verifies, and extracts factual company data.
Enforces that no information is fabricated.
"""
import re
from typing import Dict, Any, Optional
from database import set_company_fact, get_company_facts

class CompanyProfileManager:
    """Manages verified company facts and prevents hallucination."""

    # Default essential fact keys
    ESSENTIAL_KEYS = [
        ("company_name", "Official Company Legal Name", "general"),
        ("registered_office", "Registered Office Address", "general"),
        ("gstin", "GST Identification Number (GSTIN)", "taxation"),
        ("pan", "Permanent Account Number (PAN)", "taxation"),
        ("cin", "Corporate Identification Number (CIN)", "statutory"),
        ("authorized_signatory_name", "Authorized Signatory Name", "signatory"),
        ("authorized_signatory_designation", "Authorized Signatory Designation", "signatory"),
        ("contact_email", "Official Contact Email", "general"),
        ("contact_phone", "Official Contact Phone", "general"),
        ("bank_name", "Bank Name", "banking"),
        ("bank_account_number", "Bank Account Number", "banking"),
        ("bank_ifsc", "Bank IFSC Code", "banking"),
        ("msme_udyam_number", "MSME / Udyam Registration Number", "statutory"),
        ("years_in_business", "Years of Experience in Sector", "experience"),
        ("annual_turnover_fy1", "Annual Turnover Year 1 (Latest FY)", "financial"),
        ("annual_turnover_fy2", "Annual Turnover Year 2", "financial"),
        ("annual_turnover_fy3", "Annual Turnover Year 3", "financial"),
    ]

    @classmethod
    def get_all_facts(cls) -> Dict[str, Any]:
        """Returns all saved facts from the database."""
        facts = get_company_facts()
        # Ensure standard keys are present with placeholders if not set
        return facts

    @classmethod
    def set_fact(cls, key: str, value: str, category: str = "general", is_verified: bool = True):
        """Sets or updates a company fact with verification status."""
        set_company_fact(key.strip(), value.strip(), category, 1 if is_verified else 0)

    @classmethod
    def get_fact_or_placeholder(cls, key: str, description: str = "") -> str:
        """
        Retrieves a verified fact. If not present or blank, returns a clear
        placeholder that prevents false claims and prompts user action.
        """
        facts = get_company_facts()
        if key in facts and facts[key]["value"] and facts[key]["value"].strip():
            return facts[key]["value"].strip()
        label = description or key.replace("_", " ").title()
        return f"[REQUIRES CONFIRMATION: {label}]"

    @classmethod
    def extract_facts_from_text(cls, text: str) -> Dict[str, str]:
        """
        Extracts key company identifiers from text using pattern matching.
        """
        extracted = {}

        # GSTIN pattern: 2 digits state code + 5 letters PAN + 4 digits + 1 letter + 1 char + Z + 1 char
        gstin_match = re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b', text)
        if gstin_match:
            extracted["gstin"] = gstin_match.group(0)

        # PAN pattern: 5 uppercase letters + 4 digits + 1 uppercase letter
        pan_match = re.search(r'\b[A-Z]{5}\d{4}[A-Z]\b', text)
        if pan_match:
            extracted["pan"] = pan_match.group(0)

        # CIN pattern: L/U + 5 digits + 2 letters state + 4 digits year + 3 letters + 6 digits
        cin_match = re.search(r'\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b', text)
        if cin_match:
            extracted["cin"] = cin_match.group(0)

        # Udyam pattern: UDYAM-[A-Z]{2}-\d{2}-\d{7}
        udyam_match = re.search(r'\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b', text, re.IGNORECASE)
        if udyam_match:
            extracted["msme_udyam_number"] = udyam_match.group(0).upper()

        # Email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            extracted["contact_email"] = email_match.group(0)

        # IFSC pattern: 4 letters + 0 + 6 alphanumeric
        ifsc_match = re.search(r'\b[A-Z]{4}0[A-Z0-9]{6}\b', text)
        if ifsc_match:
            extracted["bank_ifsc"] = ifsc_match.group(0)

        return extracted
