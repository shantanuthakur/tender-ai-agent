"""
Tests for document parsers (PDF, DOCX, XLSX, TXT).
"""
import pytest
from pathlib import Path
import docx
import openpyxl
from parsers.document_extractor import DocumentExtractor
from parsers.docx_parser import DocxParser
from parsers.excel_parser import ExcelParser

def test_docx_parser(tmp_path):
    doc_path = tmp_path / "test_doc.docx"
    doc = docx.Document()
    doc.add_heading("ANNEXURE-I: BID COVERING LETTER", level=1)
    doc.add_paragraph("With reference to Tender No: GEM/2024/B/99999, we submit our bid.")
    doc.add_paragraph("For and on behalf of Test Company Pvt Ltd\nAuthorized Signatory")
    doc.save(str(doc_path))

    parsed = DocxParser.parse(doc_path)
    assert parsed["error"] is None
    assert "GEM/2024/B/99999" in parsed["text"]
    assert len(parsed["headings"]) >= 1
    assert len(parsed["signature_blocks"]) >= 1

def test_excel_parser(tmp_path):
    xls_path = tmp_path / "test_boq.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["Item No", "Item Description", "Qty", "Unit Price"])
    ws.append(["1", "High Performance AI Compute Server", "5", "500000"])
    wb.save(str(xls_path))

    parsed = ExcelParser.parse(xls_path)
    assert parsed["error"] is None
    assert parsed["has_boq"] is True
    assert "High Performance AI Compute Server" in parsed["text"]

def test_document_extractor_text_file(tmp_path):
    txt_path = tmp_path / "atc_clause.txt"
    txt_path.write_text("Buyer Added ATC: 1. Bidder must submit Non-Blacklisting certificate.", encoding="utf-8")

    extracted = DocumentExtractor.extract(txt_path)
    assert extracted["file_type"] == "text"
    assert "Non-Blacklisting" in extracted["text"]
