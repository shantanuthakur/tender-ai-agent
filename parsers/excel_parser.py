"""
Excel parser for BOQ, financial schedules, and compliance spreadsheets.
"""
from pathlib import Path
from typing import Dict, Any, List
import openpyxl

class ExcelParser:
    """Extracts text and tabular content from XLSX/XLS spreadsheets."""

    @staticmethod
    def parse(file_path: Path) -> Dict[str, Any]:
        result = {
            "text": "",
            "sheets": [],
            "sheet_count": 0,
            "has_boq": False,
            "error": None
        }

        try:
            wb = openpyxl.load_workbook(str(file_path), data_only=True)
            result["sheet_count"] = len(wb.sheetnames)

            text_parts: List[str] = []

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                rows_data = []

                for row in sheet.iter_rows(values_only=True):
                    # Filter out completely empty rows
                    if any(cell is not None and str(cell).strip() != "" for cell in row):
                        cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
                        rows_data.append(cleaned_row)

                if "boq" in sheet_name.lower() or "price" in sheet_name.lower() or "schedule" in sheet_name.lower():
                    result["has_boq"] = True

                sheet_info = {
                    "sheet_name": sheet_name,
                    "row_count": len(rows_data),
                    "headers": rows_data[0] if rows_data else [],
                    "sample_rows": rows_data[:10]
                }
                result["sheets"].append(sheet_info)

                # Format text
                sheet_text = f"--- [Sheet: {sheet_name}] ---\n"
                sheet_text += "\n".join(["\t".join(r) for r in rows_data[:150]]) # cap at first 150 rows for prompt sanity
                if len(rows_data) > 150:
                    sheet_text += f"\n... [{len(rows_data) - 150} more rows truncated for brevity] ..."
                text_parts.append(sheet_text)

            result["text"] = "\n\n".join(text_parts)

        except Exception as ex:
            result["error"] = f"Failed to extract Excel spreadsheet: {str(ex)}"

        return result
