"""
Template-preserving DOCX document generator using python-docx.
"""
from pathlib import Path
import re
from typing import Dict, Any, List, Optional
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

class DocxGenerator:
    """Generates Word documents preserving template layout, headers, footers, and styles."""

    @classmethod
    def generate_from_template(
        cls,
        template_path: Path,
        output_path: Path,
        replacements: Dict[str, str],
        body_sections: Optional[List[Dict[str, Any]]] = None
    ) -> Path:
        """
        Loads an existing company template, replaces variables in runs,
        paragraphs, headers, footers, and tables, without modifying the original template.
        """
        doc = docx.Document(str(template_path))

        # 1. Replace variables in all paragraphs
        for p in doc.paragraphs:
            cls._replace_in_paragraph(p, replacements)

        # 2. Replace variables in all tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        cls._replace_in_paragraph(p, replacements)

        # 3. Replace variables in headers & footers
        for section in doc.sections:
            if section.header:
                for p in section.header.paragraphs:
                    cls._replace_in_paragraph(p, replacements)
            if section.footer:
                for p in section.footer.paragraphs:
                    cls._replace_in_paragraph(p, replacements)

        # 4. If body_sections are provided and a placeholder {{body_content}} or {{content}} exists,
        # replace it; otherwise if the template is an empty shell/letterhead, append content.
        body_inserted = False
        for p in doc.paragraphs:
            if "{{body_content}}" in p.text or "{{content}}" in p.text or "[DOCUMENT_BODY]" in p.text:
                p.text = ""  # Clear placeholder
                if body_sections:
                    cls._insert_sections(doc, p, body_sections)
                body_inserted = True
                break

        if not body_inserted and body_sections and len(doc.paragraphs) <= 4:
            # Short header/letterhead template: append body sections before final signature
            for section in body_sections:
                if section.get("heading"):
                    h = doc.add_paragraph(section["heading"], style="Heading 2")
                    h.paragraph_format.space_before = Pt(8)
                    h.paragraph_format.space_after = Pt(4)
                for para in section.get("paragraphs", []):
                    p = doc.add_paragraph(para)
                    p.paragraph_format.space_after = Pt(6)
                    p.paragraph_format.line_spacing = 1.15

        # Save to output (original template untouched)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path

    @classmethod
    def generate_standard_document(
        cls,
        output_path: Path,
        title: str,
        tender_number: str,
        buyer_name: str,
        company_name: str,
        body_sections: List[Dict[str, Any]],
        signature_block: str,
        font_name: str = "Calibri"
    ) -> Path:
        """
        Creates a clean, professional corporate document when no existing company template exists.
        Flags that this is a standard layout awaiting user approval.
        """
        doc = docx.Document()

        # Set 1-inch margins
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)

        # Header note
        header = doc.sections[0].header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run(f"Standard GeM Tender Submission | {tender_number}")
        hrun.font.name = font_name
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(128, 128, 128)

        # Company Header / Letterhead Block
        p_comp = doc.add_paragraph()
        p_comp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_comp = p_comp.add_run(company_name.upper())
        run_comp.font.name = font_name
        run_comp.font.size = Pt(14)
        run_comp.font.bold = True
        run_comp.font.color.rgb = RGBColor(16, 44, 87) # Deep corporate navy

        p_line = doc.add_paragraph()
        p_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_line.paragraph_format.space_after = Pt(14)
        r_line = p_line.add_run("―" * 55)
        r_line.font.color.rgb = RGBColor(180, 180, 180)

        # Document Title
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_title.paragraph_format.space_after = Pt(6)
        r_title = p_title.add_run(title.upper())
        r_title.font.name = font_name
        r_title.font.size = Pt(12)
        r_title.font.bold = True

        # Reference line in body
        p_ref = doc.add_paragraph()
        p_ref.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_ref.paragraph_format.space_after = Pt(12)
        r_ref = p_ref.add_run(f"Reference Tender / Bid No: {tender_number} | Buyer: {buyer_name}")
        r_ref.font.name = font_name
        r_ref.font.size = Pt(10)
        r_ref.font.italic = True

        # Reference Metadata Table / Box
        meta_table = doc.add_table(rows=2, cols=2)
        meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        meta_table.autofit = True

        r1c1, r1c2 = meta_table.rows[0].cells
        r2c1, r2c2 = meta_table.rows[1].cells

        r1c1.text = f"Tender / Bid No: {tender_number}"
        r1c2.text = f"Date: [Current Date]"
        r2c1.text = f"Buyer / Department: {buyer_name}"
        r2c2.text = f"Bidder: {company_name}"

        for row in meta_table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.space_after = Pt(3)
                    for r in p.runs:
                        r.font.name = font_name
                        r.font.size = Pt(9.5)

        doc.add_paragraph().paragraph_format.space_after = Pt(10)

        # Body Sections
        for sec in body_sections:
            if sec.get("heading"):
                p_h = doc.add_paragraph()
                p_h.paragraph_format.space_before = Pt(8)
                p_h.paragraph_format.space_after = Pt(4)
                r_h = p_h.add_run(sec["heading"])
                r_h.font.name = font_name
                r_h.font.size = Pt(11)
                r_h.font.bold = True

            for p_text in sec.get("paragraphs", []):
                p_body = doc.add_paragraph()
                p_body.paragraph_format.space_after = Pt(6)
                p_body.paragraph_format.line_spacing = 1.15
                r_body = p_body.add_run(p_text)
                r_body.font.name = font_name
                r_body.font.size = Pt(10)

            # Optional table in section (e.g. compliance matrix)
            if sec.get("table"):
                tbl_data = sec["table"]
                if tbl_data:
                    doc_tbl = doc.add_table(rows=len(tbl_data), cols=len(tbl_data[0]))
                    doc_tbl.style = "Table Grid"
                    for row_idx, row_vals in enumerate(tbl_data):
                        for col_idx, cell_val in enumerate(row_vals):
                            cell = doc_tbl.rows[row_idx].cells[col_idx]
                            cell.text = str(cell_val)
                            for cp in cell.paragraphs:
                                cp.paragraph_format.space_after = Pt(2)
                                for cr in cp.runs:
                                    cr.font.name = font_name
                                    cr.font.size = Pt(9)
                                    if row_idx == 0:
                                        cr.font.bold = True
                    doc.add_paragraph().paragraph_format.space_after = Pt(8)

        # Signature Block
        doc.add_paragraph().paragraph_format.space_after = Pt(14)
        p_sig = doc.add_paragraph()
        p_sig.paragraph_format.space_before = Pt(12)
        p_sig.paragraph_format.line_spacing = 1.15
        p_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Format signature lines
        sig_lines = signature_block.split("\n")
        for line in sig_lines:
            r = p_sig.add_run(line + "\n")
            r.font.name = font_name
            r.font.size = Pt(10)
            if "Authorized Signatory" in line or "For and on behalf" in line:
                r.font.bold = True

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path

    @classmethod
    def _replace_in_paragraph(cls, paragraph, replacements: Dict[str, str]):
        """Robust replacement handling in docx paragraphs."""
        full_text = paragraph.text
        if not full_text:
            return

        modified = full_text
        for key, val in replacements.items():
            if key in modified:
                modified = modified.replace(key, val)

        if modified != full_text:
            # To preserve font styling of first run if available:
            if paragraph.runs:
                first_font = paragraph.runs[0].font.name
                first_size = paragraph.runs[0].font.size
                paragraph.text = modified
                if first_font:
                    for r in paragraph.runs:
                        r.font.name = first_font
                if first_size:
                    for r in paragraph.runs:
                        r.font.size = first_size
            else:
                paragraph.text = modified

    @classmethod
    def _insert_sections(cls, doc, anchor_paragraph, sections: List[Dict[str, Any]]):
        """Inserts sections at an anchor paragraph position."""
        for sec in sections:
            if sec.get("heading"):
                doc.add_paragraph(sec["heading"], style="Heading 2")
            for p_text in sec.get("paragraphs", []):
                doc.add_paragraph(p_text)
