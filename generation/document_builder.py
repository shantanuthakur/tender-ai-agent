"""
Orchestrator for preparing all applicable tender bid documents.
Maps requirements to templates, invokes AI drafting, saves editable files,
and records missing confirmation items.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from config import PROJECTS_DIR
from database import (
    get_tender_project,
    add_generated_document,
    record_missing_information,
    get_company_facts
)
from company.template_library import TemplateLibrary
from company.style_analyzer import StyleAnalyzer
from tender.requirement_matrix import RequirementMatrix
from generation.docx_generator import DocxGenerator
from generation.excel_generator import ExcelGenerator
from generation.ai_agent import AIAgent

class DocumentBuilder:
    """Orchestrates generation of all required tender documents."""

    DOC_TYPE_CONFIG = {
        "covering_letter": {
            "title": "Bid Covering Letter & Official Submission",
            "filename": "01_Covering_Letter.docx"
        },
        "non_blacklisting": {
            "title": "Non-Blacklisting & Non-Debarment Affidavit",
            "filename": "02_Non_Blacklisting_Declaration.docx"
        },
        "undertaking": {
            "title": "Undertaking for Compliance of Tender Terms & ATC",
            "filename": "03_ATC_Acceptance_Undertaking.docx"
        },
        "eligibility_declaration": {
            "title": "Local Content (Make in India) Declaration",
            "filename": "04_Local_Content_MII_Declaration.docx"
        },
        "technical_compliance": {
            "title": "Technical Specification Compliance Statement",
            "filename": "05_Technical_Compliance_Statement.docx"
        },
        "turnover_certificate": {
            "title": "Annual Financial Turnover Statement",
            "filename": "06_Annual_Turnover_Statement.docx"
        },
        "past_experience": {
            "title": "Statement of Past Experience & Performance",
            "filename": "07_Past_Experience_Track_Record.docx"
        },
        "oem_authorization": {
            "title": "Manufacturer's Authorization Form (MAF)",
            "filename": "08_OEM_Authorization_MAF.docx"
        },
        "company_profile": {
            "title": "Comprehensive Company Profile & Credentials",
            "filename": "09_Company_Profile_and_Registrations.docx"
        }
    }

    @classmethod
    def prepare_all_documents(cls, project_id: int, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Processes all requirements for a project and prepares every applicable bid document.
        """
        project = get_tender_project(project_id)
        if not project:
            raise ValueError(f"Project #{project_id} not found.")

        tender_number = project.get("tender_number") or "GEM/2024/B/TENDER"
        buyer_name = project.get("buyer_name") or "Government Buyer"
        requirements = RequirementMatrix.get_matrix(project_id)

        # Output directory for this project
        output_dir = PROJECTS_DIR / str(project_id) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Group requirements by suggested_doc_type
        grouped_reqs: Dict[str, List[Dict[str, Any]]] = {}
        for r in requirements:
            dtype = r.get("suggested_doc_type") or "other"
            if dtype not in grouped_reqs:
                grouped_reqs[dtype] = []
            grouped_reqs[dtype].append(r)

        company_facts = get_company_facts()
        company_name = company_facts.get("company_name", {}).get("value") or "[REQUIRES CONFIRMATION: Company Name]"
        gstin = company_facts.get("gstin", {}).get("value") or "[REQUIRES CONFIRMATION: GSTIN]"
        pan = company_facts.get("pan", {}).get("value") or "[REQUIRES CONFIRMATION: PAN]"
        cin = company_facts.get("cin", {}).get("value") or "[REQUIRES CONFIRMATION: CIN]"
        address = company_facts.get("registered_office", {}).get("value") or "[REQUIRES CONFIRMATION: Registered Office Address]"
        signatory_name = company_facts.get("authorized_signatory_name", {}).get("value") or "[REQUIRES CONFIRMATION: Authorized Signatory Name]"
        signatory_desig = company_facts.get("authorized_signatory_designation", {}).get("value") or "[REQUIRES CONFIRMATION: Signatory Designation]"

        style_profile = StyleAnalyzer.synthesize_style_profile()
        signature_block = (
            f"For and on behalf of {company_name}\n\n"
            f"_____________________________________\n"
            f"(Authorized Signatory)\n"
            f"Name: {signatory_name}\n"
            f"Designation: {signatory_desig}\n"
            f"Date: {datetime.now().strftime('%d-%b-%Y')}\n"
            f"Place: [City]\n"
            f"[Official Stamp / Seal of Bidder]"
        )

        generated_results: List[Dict[str, Any]] = []

        for doc_type, req_list in grouped_reqs.items():
            cfg = cls.DOC_TYPE_CONFIG.get(doc_type, {
                "title": f"Annexure - {doc_type.replace('_', ' ').title()}",
                "filename": f"Annexure_{doc_type}.docx"
            })
            doc_title = cfg["title"]
            target_docx = output_dir / cfg["filename"]

            # 1. Search for best template
            matched_template = TemplateLibrary.find_best_template(doc_type)

            # 2. Draft content via AIAgent
            body_sections, missing_placeholders = AIAgent.draft_document_content(
                doc_type=doc_type,
                doc_title=doc_title,
                tender_number=tender_number,
                buyer_name=buyer_name,
                requirements=req_list,
                template_doc=matched_template,
                api_key=api_key
            )

            # 3. Generate file
            if matched_template and Path(matched_template["filepath"]).exists():
                template_path = Path(matched_template["filepath"])
                template_label = f"Company Template: {matched_template['filename']}"
                replacements = {
                    "{{tender_number}}": tender_number,
                    "{{buyer_name}}": buyer_name,
                    "{{company_name}}": company_name,
                    "{{gstin}}": gstin,
                    "{{pan}}": pan,
                    "{{cin}}": cin,
                    "{{address}}": address,
                    "{{signatory_name}}": signatory_name,
                    "{{signatory_desig}}": signatory_desig,
                    "{{current_date}}": datetime.now().strftime("%d-%b-%Y")
                }
                DocxGenerator.generate_from_template(
                    template_path=template_path,
                    output_path=target_docx,
                    replacements=replacements,
                    body_sections=body_sections
                )
            else:
                template_label = "None (Proposed Standard GeM Layout - Pending Your Review)"
                DocxGenerator.generate_standard_document(
                    output_path=target_docx,
                    title=doc_title,
                    tender_number=tender_number,
                    buyer_name=buyer_name,
                    company_name=company_name,
                    body_sections=body_sections,
                    signature_block=signature_block,
                    font_name=style_profile.get("primary_font", "Calibri")
                )

            # 4. Record missing information items
            for placeholder in missing_placeholders:
                record_missing_information(
                    project_id=project_id,
                    placeholder_key=placeholder,
                    description=f"Required in {doc_title} for tender compliance",
                    target_doc=target_docx.name
                )

            # 5. Save generated document in DB
            req_ids = [r["id"] for r in req_list if "id" in r]
            gid = add_generated_document(
                project_id=project_id,
                doc_title=doc_title,
                doc_type="docx",
                template_used=template_label,
                filepath=str(target_docx.resolve()),
                requirement_ids=req_ids,
                missing_placeholders=missing_placeholders,
                verification_notes=f"Drafted based on tender requirement. {len(missing_placeholders)} pending confirmation item(s)."
            )

            generated_results.append({
                "id": gid,
                "title": doc_title,
                "file": target_docx.name,
                "path": str(target_docx.resolve()),
                "template_used": template_label,
                "missing_count": len(missing_placeholders)
            })

            # Companion Excel for technical compliance
            if doc_type == "technical_compliance":
                excel_name = "05_Technical_Compliance_Matrix.xlsx"
                excel_path = output_dir / excel_name
                ExcelGenerator.generate_compliance_sheet(
                    output_path=excel_path,
                    tender_number=tender_number,
                    buyer_name=buyer_name,
                    company_name=company_name,
                    parameters=[]
                )
                egid = add_generated_document(
                    project_id=project_id,
                    doc_title="Technical Compliance Spreadsheet (Matrix)",
                    doc_type="xlsx",
                    template_used="Standard GeM Commercial & Specification Matrix",
                    filepath=str(excel_path.resolve()),
                    requirement_ids=req_ids,
                    missing_placeholders=[],
                    verification_notes="Tabular Excel sheet for line-item technical parameter evaluation."
                )
                generated_results.append({
                    "id": egid,
                    "title": "Technical Compliance Spreadsheet (Matrix)",
                    "file": excel_name,
                    "path": str(excel_path.resolve()),
                    "template_used": "Standard GeM Matrix",
                    "missing_count": 0
                })

        return generated_results
