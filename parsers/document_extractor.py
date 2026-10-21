"""
Unified document extraction interface for all tender and company document formats.
"""
from pathlib import Path
from typing import Dict, Any
from parsers.pdf_parser import PDFParser
from parsers.docx_parser import DocxParser
from parsers.excel_parser import ExcelParser

class DocumentExtractor:
    """Routes files to appropriate parsers and extracts structured content."""

    @classmethod
    def extract(cls, file_path: str | Path) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {
                "filename": path.name,
                "file_type": "unknown",
                "text": "",
                "error": f"File not found: {path}"
            }

        suffix = path.suffix.lower()
        base_meta = {
            "filename": path.name,
            "filepath": str(path.resolve()),
            "file_size": path.stat().st_size,
            "extension": suffix
        }

        if suffix == ".pdf":
            parsed = PDFParser.parse(path)
            base_meta["file_type"] = "pdf"
        elif suffix in [".docx", ".doc"]:
            parsed = DocxParser.parse(path)
            base_meta["file_type"] = "docx"
        elif suffix in [".xlsx", ".xls", ".csv"]:
            parsed = ExcelParser.parse(path)
            base_meta["file_type"] = "excel"
        elif suffix in [".txt", ".md", ".json"]:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                parsed = {"text": text, "error": None}
            except Exception as e:
                parsed = {"text": "", "error": f"Error reading text file: {e}"}
            base_meta["file_type"] = "text"
        else:
            parsed = {
                "text": "",
                "error": f"Unsupported file extension '{suffix}'. Supported: PDF, DOCX, XLSX, XLS, TXT, CSV."
            }
            base_meta["file_type"] = "unsupported"

        # Merge base_meta and parsed
        combined = {**base_meta, **parsed}
        return combined
