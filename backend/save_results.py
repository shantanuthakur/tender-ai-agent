"""
Results Saver Module
Saves filtered tender results to:
- Excel (.xlsx) — formatted spreadsheet with color-coded confidence
- Word (.docx) — professional tender report document
- JSON — machine-readable backup
Also maintains a deduplication log across runs.
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
LOG_FILE = os.path.join(OUTPUT_DIR, "tenders_log.json")


def _ensure_output_dir():
    """Create the output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DEDUPLICATION LOG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_seen_bids() -> set:
    """Load previously seen bid numbers from the log file."""
    if not os.path.exists(LOG_FILE):
        return set()

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("seen_bid_numbers", []))
    except (json.JSONDecodeError, KeyError):
        return set()


def save_seen_bids(seen_bids: set):
    """Save seen bid numbers to the log file."""
    _ensure_output_dir()
    data = {
        "last_updated": datetime.now().isoformat(),
        "total_seen": len(seen_bids),
        "seen_bid_numbers": sorted(list(seen_bids)),
    }
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def filter_new_bids(bids: list[dict], seen_bids: set) -> list[dict]:
    """
    Filter out bids that have already been processed.

    Args:
        bids: All scraped bids.
        seen_bids: Set of previously seen bid numbers.

    Returns:
        List of new (unseen) bids.
    """
    new_bids = []
    for bid in bids:
        bid_num = bid.get("bid_number", "")
        if bid_num and bid_num not in seen_bids:
            new_bids.append(bid)
        elif not bid_num:
            # Bids without numbers are always included (can't deduplicate)
            new_bids.append(bid)

    logger.info(
        f"📋 {len(new_bids)} new bids out of {len(bids)} total "
        f"(filtered {len(bids) - len(new_bids)} duplicates)"
    )
    return new_bids


def update_seen_log(bids: list[dict]):
    """
    Update the deduplication log with newly processed bid numbers.

    Args:
        bids: List of bids that have been processed.
    """
    seen = load_seen_bids()
    for bid in bids:
        bid_num = bid.get("bid_number", "")
        if bid_num:
            seen.add(bid_num)
    save_seen_bids(seen)
    logger.info(f"📝 Updated dedup log. Total tracked bids: {len(seen)}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EXCEL REPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_to_excel(bids: list[dict], filename: str = None) -> str:
    """
    Save relevant tender bids to a formatted Excel file.

    Args:
        bids: List of relevant bid dictionaries.
        filename: Optional custom filename. Defaults to timestamped name.

    Returns:
        Path to the saved Excel file.
    """
    _ensure_output_dir()

    if not filename:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"relevant_tenders_{timestamp}.xlsx"

    filepath = os.path.join(OUTPUT_DIR, filename)

    wb = Workbook()
    ws = wb.active
    ws.title = "Relevant Tenders"

    # ─── Define styles ──────────────────────────────────────────
    header_font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    data_font = Font(name="Calibri", size=10)
    data_alignment = Alignment(vertical="top", wrap_text=True)

    link_font = Font(name="Calibri", size=10, color="0563C1", underline="single")

    high_conf_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    medium_conf_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
    low_conf_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
    fallback_fill = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    # ─── Column definitions ─────────────────────────────────────
    columns = [
        ("S.No", 6),
        ("Bid Number", 25),
        ("Title / Description", 50),
        ("Matched Product", 25),
        ("Department", 35),
        ("Quantity", 15),
        ("Start Date", 18),
        ("End Date", 18),
        ("Bid Value", 18),
        ("AI Confidence", 14),
        ("AI Reason", 40),
        ("Detail Link", 55),
    ]

    # ─── Title row ──────────────────────────────────────────────
    title_font = Font(name="Calibri", size=16, bold=True, color="1B2A4A")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    title_cell = ws.cell(
        row=1, column=1,
        value="GeM Tender Results — Mobile Light Tower & Inflatable Light Systems"
    )
    title_cell.font = title_font
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    # Subtitle with run info
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))
    subtitle = (
        f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}  |  "
        f"Total Relevant: {len(bids)}"
    )
    subtitle_cell = ws.cell(row=2, column=1, value=subtitle)
    subtitle_cell.font = Font(name="Calibri", size=10, italic=True, color="666666")
    subtitle_cell.alignment = Alignment(horizontal="center")

    # ─── Headers ────────────────────────────────────────────────
    header_row = 4
    for col_idx, (col_name, col_width) in enumerate(columns, 1):
        cell = ws.cell(row=header_row, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width

    # ─── Data rows ──────────────────────────────────────────────
    for row_idx, bid in enumerate(bids, 1):
        data_row = header_row + row_idx

        confidence = bid.get("ai_confidence", "unknown")

        # Determine row background based on confidence
        row_fill = None
        if confidence == "high":
            row_fill = high_conf_fill
        elif confidence == "medium":
            row_fill = medium_conf_fill
        elif confidence == "low":
            row_fill = low_conf_fill
        elif confidence == "fallback":
            row_fill = fallback_fill

        row_data = [
            row_idx,
            bid.get("bid_number", "N/A"),
            bid.get("title", "N/A"),
            bid.get("matched_product", ""),
            bid.get("department", "N/A"),
            bid.get("quantity", "N/A"),
            bid.get("start_date", "N/A"),
            bid.get("end_date", "N/A"),
            bid.get("bid_value", "N/A"),
            confidence.capitalize(),
            bid.get("ai_reason", ""),
            bid.get("detail_link", ""),
        ]

        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=data_row, column=col_idx, value=value)
            cell.font = data_font
            cell.alignment = data_alignment
            cell.border = thin_border

            if row_fill:
                cell.fill = row_fill

        # Make the detail link clickable
        link = bid.get("detail_link", "")
        if link:
            link_cell = ws.cell(row=data_row, column=len(columns))
            link_cell.hyperlink = link
            link_cell.font = link_font

    # ─── Auto-filter ────────────────────────────────────────────
    if bids:
        last_row = header_row + len(bids)
        ws.auto_filter.ref = (
            f"A{header_row}:{get_column_letter(len(columns))}{last_row}"
        )

    # ─── Freeze panes (freeze header) ──────────────────────────
    ws.freeze_panes = f"A{header_row + 1}"

    # ─── Summary sheet ──────────────────────────────────────────
    ws_summary = wb.create_sheet("Summary")
    summary_data = [
        ["GeM Tender AI Agent — Run Summary"],
        [""],
        ["Run Date", datetime.now().strftime("%d %b %Y, %I:%M %p")],
        ["Total Relevant Tenders", len(bids)],
        ["High Confidence", sum(1 for b in bids if b.get("ai_confidence") == "high")],
        ["Medium Confidence", sum(1 for b in bids if b.get("ai_confidence") == "medium")],
        ["Low Confidence", sum(1 for b in bids if b.get("ai_confidence") == "low")],
        ["Keyword Fallback", sum(1 for b in bids if b.get("ai_confidence") == "fallback")],
        [""],
        ["Products Searched For:"],
        ["Mobile Lighting Tower Systems (MST / MLT)"],
        ["Inflatable Lighting Tower Systems / Balloon Lights"],
        ["Portable LED Tower Lights / Floodlight Towers"],
        ["Telescopic Light Masts / Light Mast Systems"],
        ["Mobile Solar Tower Lighting"],
    ]

    for row_idx, row_data in enumerate(summary_data, 1):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws_summary.cell(row=row_idx, column=col_idx, value=value)
            if row_idx == 1:
                cell.font = Font(name="Calibri", size=14, bold=True, color="1B2A4A")
            elif col_idx == 1 and row_idx >= 3:
                cell.font = Font(name="Calibri", size=10, bold=True)

    ws_summary.column_dimensions["A"].width = 35
    ws_summary.column_dimensions["B"].width = 30

    # ─── Save ───────────────────────────────────────────────────
    wb.save(filepath)
    logger.info(f"💾 Excel file saved: {filepath}")
    return filepath


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WORD DOCUMENT REPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_to_word(bids: list[dict], filename: str = None) -> str:
    """
    Save relevant tender bids to a professional Word document (.docx).

    Creates a detailed report with:
    - Title page
    - Summary statistics table
    - Individual tender detail sections

    Args:
        bids: List of relevant bid dictionaries.
        filename: Optional custom filename.

    Returns:
        Path to the saved Word file.
    """
    _ensure_output_dir()

    if not filename:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"relevant_tenders_{timestamp}.docx"

    filepath = os.path.join(OUTPUT_DIR, filename)

    doc = Document()

    # ─── Document margins ───────────────────────────────────────
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # ─── Title Page ─────────────────────────────────────────────
    _add_title_page(doc, bids)

    # ─── Summary Section ───────────────────────────────────────
    doc.add_page_break()
    _add_summary_section(doc, bids)

    # ─── Tender Details ─────────────────────────────────────────
    if bids:
        doc.add_page_break()
        heading = doc.add_heading("Tender Details", level=1)
        _style_heading(heading, "1B2A4A")

        for i, bid in enumerate(bids, 1):
            _add_tender_card(doc, bid, i)

            # Add a page break between tenders (except after the last one)
            if i < len(bids):
                doc.add_paragraph()  # Small spacing

    # ─── Save ───────────────────────────────────────────────────
    doc.save(filepath)
    logger.info(f"💾 Word document saved: {filepath}")
    return filepath


def _add_title_page(doc: Document, bids: list[dict]):
    """Add a title page to the document."""
    # Add some spacing at the top
    for _ in range(4):
        doc.add_paragraph()

    # Main title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("GeM Tender Report")
    run.font.size = Pt(32)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1B, 0x2A, 0x4A)

    # Subtitle
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Mobile Light Tower & Inflatable Light Systems")
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0x3D, 0x5A, 0x80)

    doc.add_paragraph()

    # Horizontal line
    hr = doc.add_paragraph()
    hr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = hr.add_run("━" * 50)
    run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    run.font.size = Pt(10)

    doc.add_paragraph()

    # Info box
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info.add_run(f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}")
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    info2 = doc.add_paragraph()
    info2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info2.add_run(f"Total Relevant Tenders Found: {len(bids)}")
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x27, 0xAE, 0x60)

    doc.add_paragraph()

    # Source
    src = doc.add_paragraph()
    src.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = src.add_run("Source: GeM Portal (bidplus.gem.gov.in)")
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # Disclaimer
    doc.add_paragraph()
    disc = doc.add_paragraph()
    disc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = disc.add_run(
        "This report was generated by the GeM Tender AI Agent. "
        "AI-based relevance analysis may not be 100% accurate. "
        "Please verify individual tenders on the GeM portal."
    )
    run.font.size = Pt(8)
    run.font.italic = True
    run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)


def _add_summary_section(doc: Document, bids: list[dict]):
    """Add a summary statistics section."""
    heading = doc.add_heading("Summary", level=1)
    _style_heading(heading, "1B2A4A")

    high = sum(1 for b in bids if b.get("ai_confidence") == "high")
    medium = sum(1 for b in bids if b.get("ai_confidence") == "medium")
    low = sum(1 for b in bids if b.get("ai_confidence") == "low")
    fallback = sum(1 for b in bids if b.get("ai_confidence") == "fallback")

    # Summary table
    table = doc.add_table(rows=6, cols=2)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    summary_rows = [
        ("Metric", "Value"),
        ("Total Relevant Tenders", str(len(bids))),
        ("High Confidence", str(high)),
        ("Medium Confidence", str(medium)),
        ("Low Confidence", str(low)),
        ("Keyword Fallback", str(fallback)),
    ]

    for i, (label, value) in enumerate(summary_rows):
        row = table.rows[i]
        row.cells[0].text = label
        row.cells[1].text = value
        if i == 0:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.bold = True

    # Set column widths
    for row in table.rows:
        row.cells[0].width = Inches(3)
        row.cells[1].width = Inches(2)

    doc.add_paragraph()

    # Product categories searched
    doc.add_heading("Products Searched", level=2)
    products = [
        "Mobile Lighting Tower Systems (MST / MLT)",
        "Inflatable Lighting Tower Systems / Balloon Lights",
        "Portable LED Tower Lights / Floodlight Towers",
        "Telescopic Light Masts / Light Mast Systems",
        "Mobile Solar Tower Lighting",
        "Emergency / Disaster Lighting Equipment",
    ]
    for product in products:
        p = doc.add_paragraph(product, style="List Bullet")
        for run in p.runs:
            run.font.size = Pt(10)


def _add_tender_card(doc: Document, bid: dict, index: int):
    """Add a single tender card to the document."""
    bid_number = bid.get("bid_number", "N/A")
    title = bid.get("title", "N/A")
    confidence = bid.get("ai_confidence", "unknown")

    # Tender heading with number
    heading = doc.add_heading(f"Tender #{index}: {bid_number}", level=2)
    _style_heading(heading, "3D5A80")

    # Confidence badge
    conf_para = doc.add_paragraph()
    conf_label = conf_para.add_run(f"AI Confidence: ")
    conf_label.font.size = Pt(10)
    conf_label.font.bold = True
    conf_value = conf_para.add_run(confidence.upper())
    conf_value.font.size = Pt(10)
    conf_value.font.bold = True
    if confidence == "high":
        conf_value.font.color.rgb = RGBColor(0x27, 0xAE, 0x60)
    elif confidence == "medium":
        conf_value.font.color.rgb = RGBColor(0xF3, 0x9C, 0x12)
    elif confidence == "low":
        conf_value.font.color.rgb = RGBColor(0xE7, 0x4C, 0x3C)
    else:
        conf_value.font.color.rgb = RGBColor(0x95, 0xA5, 0xA6)

    # Tender details table
    details = [
        ("Bid Number", bid_number),
        ("Title / Description", title),
        ("Matched Product", bid.get("matched_product", "N/A")),
        ("Department", bid.get("department", "N/A")),
        ("Quantity", bid.get("quantity", "N/A")),
        ("Start Date", bid.get("start_date", "N/A")),
        ("End Date", bid.get("end_date", "N/A")),
        ("Bid Value", bid.get("bid_value", "N/A")),
        ("AI Reason", bid.get("ai_reason", "N/A")),
    ]

    # Add full description if available
    full_desc = bid.get("full_description", "")
    if full_desc and full_desc != title:
        details.append(("Full Description", full_desc))

    # Add specifications if available
    specs = bid.get("specifications", "")
    if specs:
        details.append(("Specifications", specs))

    # Add delivery location if available
    delivery = bid.get("delivery_location", "")
    if delivery:
        details.append(("Delivery Location", delivery))

    table = doc.add_table(rows=len(details), cols=2)
    table.style = "Light Grid Accent 1"

    for i, (label, value) in enumerate(details):
        row = table.rows[i]
        # Label cell
        label_cell = row.cells[0]
        label_cell.text = label
        label_cell.width = Inches(2)
        for paragraph in label_cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x1B, 0x2A, 0x4A)

        # Value cell
        value_cell = row.cells[1]
        value_cell.text = str(value) if value else "N/A"
        value_cell.width = Inches(4.5)
        for paragraph in value_cell.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(9)

    # Detail link
    link = bid.get("detail_link", "")
    if link:
        link_para = doc.add_paragraph()
        link_run = link_para.add_run("🔗 View on GeM: ")
        link_run.font.size = Pt(9)
        link_run.font.bold = True
        link_value = link_para.add_run(link)
        link_value.font.size = Pt(9)
        link_value.font.color.rgb = RGBColor(0x05, 0x63, 0xC1)
        link_value.font.underline = True


def _style_heading(heading, color_hex: str):
    """Apply custom color to a heading."""
    for run in heading.runs:
        run.font.color.rgb = RGBColor(
            int(color_hex[0:2], 16),
            int(color_hex[2:4], 16),
            int(color_hex[4:6], 16),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  JSON EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def save_to_json(bids: list[dict], filename: str = None) -> str:
    """
    Save relevant tender bids to a JSON file (machine-readable backup).
    This is also consumed by the frontend dashboard.

    Args:
        bids: List of relevant bid dictionaries.
        filename: Optional custom filename.

    Returns:
        Path to the saved JSON file.
    """
    _ensure_output_dir()

    if not filename:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"relevant_tenders_{timestamp}.json"

    filepath = os.path.join(OUTPUT_DIR, filename)

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_relevant": len(bids),
        "summary": {
            "high_confidence": sum(1 for b in bids if b.get("ai_confidence") == "high"),
            "medium_confidence": sum(1 for b in bids if b.get("ai_confidence") == "medium"),
            "low_confidence": sum(1 for b in bids if b.get("ai_confidence") == "low"),
            "fallback": sum(1 for b in bids if b.get("ai_confidence") == "fallback"),
        },
        "bids": bids,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"💾 JSON file saved: {filepath}")

    # Also save a "latest" copy for the frontend to use
    latest_path = os.path.join(OUTPUT_DIR, "latest_results.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 Latest results symlink: {latest_path}")

    return filepath


def save_all(bids: list[dict]) -> dict:
    """
    Save results in all formats (Excel, Word, JSON) and update the dedup log.

    Args:
        bids: List of relevant bid dictionaries.

    Returns:
        Dictionary with file paths for each format.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    excel_path = save_to_excel(bids, f"relevant_tenders_{timestamp}.xlsx")
    word_path = save_to_word(bids, f"relevant_tenders_{timestamp}.docx")
    json_path = save_to_json(bids, f"relevant_tenders_{timestamp}.json")

    update_seen_log(bids)

    return {
        "excel": excel_path,
        "word": word_path,
        "json": json_path,
    }
