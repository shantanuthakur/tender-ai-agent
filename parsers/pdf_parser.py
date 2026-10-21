"""
PDF extraction module using PyPDF with fallbacks and scan detection.
"""
from pathlib import Path
from typing import Dict, Any, List

class PDFParser:
    """Extracts text and metadata from PDF files with page numbering."""

    @staticmethod
    def parse(file_path: Path) -> Dict[str, Any]:
        result = {
            "text": "",
            "pages": [],
            "page_count": 0,
            "has_scanned_pages": False,
            "scanned_page_numbers": [],
            "metadata": {},
            "error": None
        }

        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            result["page_count"] = len(reader.pages)
            if reader.metadata:
                result["metadata"] = {k: str(v) for k, v in reader.metadata.items() if v}

            extracted_pages: List[Dict[str, Any]] = []
            full_text_parts: List[str] = []

            for i, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as e:
                    text = ""

                clean_text = text.strip()
                extracted_pages.append({
                    "page_number": i,
                    "text": clean_text,
                    "char_count": len(clean_text)
                })

                if clean_text:
                    full_text_parts.append(f"--- [Page {i}] ---\n{clean_text}")

                # If page has very little or no text and has images, mark as potentially scanned
                if len(clean_text) < 40:
                    try:
                        if len(page.images) > 0:
                            result["scanned_page_numbers"].append(i)
                    except Exception:
                        result["scanned_page_numbers"].append(i)

            result["text"] = "\n\n".join(full_text_parts)
            result["pages"] = extracted_pages
            result["has_scanned_pages"] = len(result["scanned_page_numbers"]) > 0

            if not result["text"].strip() and result["page_count"] > 0:
                result["error"] = (
                    f"Document contains {result['page_count']} page(s) but no extractable digital text. "
                    f"It appears to be a scanned copy. Please provide an OCR-converted or original digital copy if possible."
                )

        except Exception as ex:
            result["error"] = f"Failed to extract PDF: {str(ex)}"

        return result
