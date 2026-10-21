"""
Tests for CompanyProfileManager and anti-hallucination placeholders.
"""
import pytest
from company.profile_manager import CompanyProfileManager

def test_company_profile_crud():
    CompanyProfileManager.set_fact("test_fact_key", "Verified Value 123", "test_cat", is_verified=True)
    facts = CompanyProfileManager.get_all_facts()
    assert "test_fact_key" in facts
    assert facts["test_fact_key"]["value"] == "Verified Value 123"

def test_anti_hallucination_placeholder():
    # If a fact key does not exist, it must return a clear REQUIRES CONFIRMATION placeholder
    placeholder = CompanyProfileManager.get_fact_or_placeholder("unverified_bank_swift_code")
    assert "[REQUIRES CONFIRMATION:" in placeholder
    assert "Unverified Bank Swift Code" in placeholder

def test_fact_extraction_from_text():
    sample_text = """
    M/s Antigravity Dynamics Ltd
    Registered Office: Connaught Place, New Delhi 110001
    GSTIN: 07AAAAA0000A1Z5
    PAN: AAAAA0000A
    CIN: L12345DL2020PLC123456
    Email: tenders@antigravitydynamics.com
    """
    extracted = CompanyProfileManager.extract_facts_from_text(sample_text)
    assert extracted.get("gstin") == "07AAAAA0000A1Z5"
    assert extracted.get("pan") == "AAAAA0000A"
    assert extracted.get("cin") == "L12345DL2020PLC123456"
    assert extracted.get("contact_email") == "tenders@antigravitydynamics.com"
