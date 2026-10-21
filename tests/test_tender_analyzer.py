"""
Tests for TenderAnalyzer and ComplianceChecker.
"""
from pathlib import Path
from tender.analyzer import TenderAnalyzer
from verification.compliance_checker import ComplianceChecker
from generation.document_builder import DocumentBuilder

def test_tender_analyzer_heuristic(tmp_path):
    project_id = TenderAnalyzer.create_project("Test GeM Project")
    assert project_id > 0

    # Create dummy tender files
    bid_doc = tmp_path / "Bid_Document_GEM_2024_B_8888.txt"
    bid_doc.write_text(
        "Government e-Marketplace\n"
        "Bid Number: GEM/2024/B/8888\n"
        "Ministry/State Name: Ministry of Electronics and Information Technology\n"
        "Bid End Date/Time: 25-11-2024 15:00:00\n"
        "Minimum Average Annual Turnover: Rs. 50 Lakhs in last 3 financial years.\n"
        "Make in India Preference applies: Class-I local supplier.\n",
        encoding="utf-8"
    )

    atc_doc = tmp_path / "Buyer_Added_Bid_Specific_ATC.txt"
    atc_doc.write_text(
        "Buyer Added ATC Clauses:\n"
        "1. Bidder must upload Non-Blacklisting certificate.\n"
        "2. Bidder must submit undertaking for unconditional acceptance of ATC.\n"
        "3. Land border sharing declaration as per Rule 144(xi) GFR 2017 is mandatory.\n",
        encoding="utf-8"
    )

    TenderAnalyzer.ingest_tender_file(project_id, bid_doc)
    TenderAnalyzer.ingest_tender_file(project_id, atc_doc)

    res = TenderAnalyzer.analyze_tender_package(project_id)
    assert res["metadata"]["tender_number"] == "GEM/2024/B/8888"
    assert "Electronics and Information Technology" in res["metadata"]["buyer_name"]
    assert len(res["requirements"]) >= 5

def test_document_builder_and_compliance(tmp_path):
    project_id = TenderAnalyzer.create_project("Integration Test Tender")

    # Ingest bid doc
    bid_file = tmp_path / "Bid_Doc.txt"
    bid_file.write_text("Bid Number: GEM/2024/B/7777\nMinistry/State Name: DRDO\nBidder must submit Non-Blacklisting affidavit.", encoding="utf-8")
    TenderAnalyzer.ingest_tender_file(project_id, bid_file)

    TenderAnalyzer.analyze_tender_package(project_id)

    # Prepare documents
    docs = DocumentBuilder.prepare_all_documents(project_id)
    assert len(docs) > 0

    # Run compliance audit
    audit = ComplianceChecker.run_compliance_audit(project_id)
    assert audit["total_requirements"] > 0
    assert audit["generated_documents_count"] > 0
    assert "AUTOMATED COMPLIANCE AUDIT COMPLETE" in audit["unresolved_risks_note"]
