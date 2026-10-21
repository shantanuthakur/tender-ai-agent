"""
Tender Analyzer: parses tender package, extracts metadata, checks corrigenda,
and generates the structured requirement matrix with source citations.
"""
from pathlib import Path
import re
import json
from typing import Dict, Any, List, Optional
from config import PROJECTS_DIR, OPENAI_API_KEY, OPENAI_MODEL
from parsers.document_extractor import DocumentExtractor
from database import (
    create_tender_project,
    get_tender_project,
    add_tender_file,
    list_tender_files,
    update_tender_project_metadata
)
from tender.requirement_matrix import RequirementMatrix

class TenderAnalyzer:
    """Analyzes all files in a tender package, maps requirements, and identifies required bid documents."""

    @classmethod
    def create_project(cls, project_name: str) -> int:
        project_id = create_tender_project(name=project_name)
        # Create project input/output directories
        proj_dir = PROJECTS_DIR / str(project_id)
        (proj_dir / "input").mkdir(parents=True, exist_ok=True)
        (proj_dir / "output").mkdir(parents=True, exist_ok=True)
        return project_id

    @classmethod
    def ingest_tender_file(cls, project_id: int, file_path: Path, filename: Optional[str] = None) -> Dict[str, Any]:
        """Saves and parses an uploaded tender file."""
        fname = filename or file_path.name
        dest_path = PROJECTS_DIR / str(project_id) / "input" / fname

        # Copy file
        with open(file_path, "rb") as src, open(dest_path, "wb") as dst:
            dst.write(src.read())

        # Extract content
        extracted = DocumentExtractor.extract(dest_path)
        text = extracted.get("text", "")
        error_msg = extracted.get("error") or ""

        # Auto-detect category
        lower_name = fname.lower()
        lower_text = text[:2000].lower()
        if "atc" in lower_name or "buyer added" in lower_text or "additional terms" in lower_text:
            category = "atc"
        elif "corrigendum" in lower_name or "amendment" in lower_name or "addendum" in lower_text:
            category = "corrigendum"
        elif "boq" in lower_name or "price" in lower_name or extracted.get("file_type") == "excel":
            category = "boq"
        elif "spec" in lower_name or "technical" in lower_name:
            category = "tech_specs"
        elif "bid" in lower_name or "gem" in lower_name:
            category = "bid_document"
        else:
            category = "general"

        page_count = extracted.get("page_count") or (1 if text else 0)

        file_id = add_tender_file(
            project_id=project_id,
            filename=fname,
            filepath=str(dest_path.resolve()),
            file_type=extracted.get("file_type", "unknown"),
            category=category,
            page_count=page_count,
            extracted_text=text,
            error_message=error_msg
        )

        return {
            "file_id": file_id,
            "filename": fname,
            "category": category,
            "page_count": page_count,
            "has_error": bool(error_msg),
            "error_message": error_msg,
            "char_count": len(text)
        }

    @classmethod
    def analyze_tender_package(cls, project_id: int, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs comprehensive analysis on all ingested tender files.
        Extracts metadata, corrigenda, and builds requirement checklist.
        """
        files = list_tender_files(project_id)
        if not files:
            return {"error": "No files uploaded for this tender project."}

        combined_text = ""
        corrigenda_texts = []
        extraction_warnings = []

        for f in files:
            fname = f["filename"]
            ftext = f.get("extracted_text") or ""
            ferr = f.get("error_message") or ""

            if ferr:
                extraction_warnings.append(f"Warning in '{fname}': {ferr}")

            if f.get("category") == "corrigendum":
                corrigenda_texts.append(f"=== CORRIGENDUM [{fname}] ===\n{ftext}")
            else:
                combined_text += f"\n\n=== FILE: {fname} ({f.get('category')}) ===\n{ftext}"

        # Combine all files with Corrigenda placed prominently
        full_tender_corpus = "\n\n".join(corrigenda_texts + [combined_text])

        # 1. Extract Core Metadata
        metadata = cls._extract_metadata(full_tender_corpus, files)

        # 2. Extract Requirements & Documents
        use_key = api_key or OPENAI_API_KEY
        if use_key and len(use_key.strip()) > 10:
            try:
                requirements = cls._extract_requirements_with_ai(full_tender_corpus, metadata, use_key)
            except Exception as e:
                # Graceful fallback to heuristic analysis if API call fails
                requirements = cls._extract_requirements_heuristics(full_tender_corpus, files)
                extraction_warnings.append(f"AI parsing failed, fell back to heuristic analysis: {str(e)}")
        else:
            requirements = cls._extract_requirements_heuristics(full_tender_corpus, files)

        # Update Project record in DB
        update_tender_project_metadata(
            project_id=project_id,
            tender_number=metadata.get("tender_number", ""),
            buyer_name=metadata.get("buyer_name", ""),
            submission_deadline=metadata.get("submission_deadline", ""),
            summary=metadata.get("summary", ""),
            status="analyzed"
        )

        # Persist requirements checklist
        RequirementMatrix.save_matrix(project_id, requirements)

        return {
            "metadata": metadata,
            "requirements": requirements,
            "files_analyzed": len(files),
            "extraction_warnings": extraction_warnings
        }

    @classmethod
    def _extract_metadata(cls, text: str, files: List[Dict]) -> Dict[str, Any]:
        """Extracts tender number, buyer, deadlines, EMD, and corrigendum notes."""
        meta = {
            "tender_number": "",
            "buyer_name": "",
            "submission_deadline": "",
            "estimated_value": "",
            "emd_amount": "",
            "pbg_percent": "",
            "summary": "",
            "corrigenda_applied": False
        }

        # Tender / Bid Number (e.g. GEM/2024/B/1234567 or GEM/202... or NIT No...)
        gem_match = re.search(r'\b(GEM/\d{4}/[B|R]/\d+)\b', text, re.IGNORECASE)
        if gem_match:
            meta["tender_number"] = gem_match.group(1).upper()
        else:
            nit_match = re.search(r'(?:Bid\s+No|Tender\s+No|NIT\s+No|Reference\s+No)[:.\s]+([A-Za-z0-9\/\-_]+)', text, re.IGNORECASE)
            if nit_match:
                meta["tender_number"] = nit_match.group(1).strip()
            else:
                meta["tender_number"] = "GEM/2024/B/PENDING-VERIFICATION"

        # Buyer Details
        buyer_match = re.search(r'(?:Ministry/State\s+Name|Department\s+Name|Organisation\s+Name|Buyer\s+Details|Purchaser)[:.\s]+([^\n\r]+)', text, re.IGNORECASE)
        if buyer_match:
            meta["buyer_name"] = buyer_match.group(1).strip()
        else:
            dept_match = re.search(r'(?:Office\s+Name|Buyer\s+Designation)[:.\s]+([^\n\r]+)', text, re.IGNORECASE)
            if dept_match:
                meta["buyer_name"] = dept_match.group(1).strip()
            else:
                meta["buyer_name"] = "Government Buyer / Procuring Department"

        # Submission Deadline (look in Corrigenda first)
        deadline_match = re.search(r'(?:Bid\s+End\s+Date/Time|Submission\s+Deadline|Last\s+Date\s+for\s+Submission)[:.\s]+([^\n\r]+)', text, re.IGNORECASE)
        if deadline_match:
            meta["submission_deadline"] = deadline_match.group(1).strip()

        # EMD / PBG
        emd_match = re.search(r'(?:EMD\s+Amount|Earnest\s+Money\s+Deposit)[:.\s]+([^\n\r]+)', text, re.IGNORECASE)
        if emd_match:
            meta["emd_amount"] = emd_match.group(1).strip()

        pbg_match = re.search(r'(?:ePBG|Performance\s+Security|PBG)[:.\s]+([^\n\r]+)', text, re.IGNORECASE)
        if pbg_match:
            meta["pbg_percent"] = pbg_match.group(1).strip()

        # Corrigenda check
        has_corrigendum = any(f.get("category") == "corrigendum" for f in files) or "corrigendum" in text.lower()
        meta["corrigenda_applied"] = has_corrigendum

        meta["summary"] = (
            f"Tender {meta['tender_number']} issued by {meta['buyer_name']}. "
            f"Deadline: {meta.get('submission_deadline', 'Refer to portal')}. "
            f"Corrigenda: {'Detected and incorporated' if has_corrigendum else 'None'}."
        )

        return meta

    @classmethod
    def _extract_requirements_heuristics(cls, text: str, files: List[Dict]) -> List[Dict[str, Any]]:
        """
        Extracts requirements and mandatory declarations using robust pattern matching
        on GeM / public tender clauses.
        """
        requirements: List[Dict[str, Any]] = []

        primary_doc = files[0]["filename"] if files else "tender_bid_document.pdf"
        atc_doc = next((f["filename"] for f in files if f.get("category") == "atc"), primary_doc)

        # 1. Covering Letter & Acceptance
        requirements.append({
            "req_type": "statutory",
            "title": "Bid Covering Letter & Official Submission",
            "description": "Formal bid submission letter on company letterhead addressed to buyer referencing tender number, confirming unconditional participation.",
            "source_doc": primary_doc,
            "source_page_section": "General Terms & Instructions",
            "mandatory": True,
            "status": "awaiting_review",
            "suggested_doc_type": "covering_letter"
        })

        # 2. Non-Blacklisting / Debarment
        requirements.append({
            "req_type": "declaration",
            "title": "Non-Blacklisting / Non-Debarment Undertaking",
            "description": "Solemn declaration that bidder is not blacklisted, debarred or banned by any Central/State Govt organization or PSU as on bid date.",
            "source_doc": atc_doc,
            "source_page_section": "Buyer Added Bid Specific ATC / Standard Clauses",
            "mandatory": True,
            "status": "awaiting_review",
            "suggested_doc_type": "non_blacklisting"
        })

        # 3. Acceptance of ATC
        requirements.append({
            "req_type": "declaration",
            "title": "Unconditional Acceptance of Buyer Added ATC",
            "description": "Signed acceptance of all Additional Terms and Conditions without deviation or reservation.",
            "source_doc": atc_doc,
            "source_page_section": "Buyer Added ATC",
            "mandatory": True,
            "status": "awaiting_review",
            "suggested_doc_type": "undertaking"
        })

        # 4. Make in India (MII) / Local Content
        if "make in india" in text.lower() or "local content" in text.lower() or "class-i" in text.lower():
            requirements.append({
                "req_type": "declaration",
                "title": "Make in India (MII) / Local Content Certificate",
                "description": "Declaration of local content percentage and place of value addition as per Public Procurement (Preference to Make in India) Order.",
                "source_doc": primary_doc,
                "source_page_section": "MII Preference Clause",
                "mandatory": True,
                "status": "awaiting_review",
                "suggested_doc_type": "eligibility_declaration"
            })

        # 5. Land Border Sharing (Rule 144(xi) GFR)
        if "land border" in text.lower() or "rule 144(xi)" in text.lower() or "border" in text.lower():
            requirements.append({
                "req_type": "declaration",
                "title": "Land Border Sharing Compliance Declaration (GFR 144(xi))",
                "description": "Undertaking regarding compliance with restrictions on procurement from bidders from countries sharing land border with India.",
                "source_doc": primary_doc,
                "source_page_section": "Statutory Order GFR 144(xi)",
                "mandatory": True,
                "status": "awaiting_review",
                "suggested_doc_type": "undertaking"
            })

        # 6. Technical Compliance Statement
        tech_doc = next((f["filename"] for f in files if f.get("category") == "tech_specs"), primary_doc)
        requirements.append({
            "req_type": "technical",
            "title": "Technical Specification Compliance Statement",
            "description": "Clause-by-clause or parameter-by-parameter compliance matrix against buyer specifications with deviation remarks.",
            "source_doc": tech_doc,
            "source_page_section": "Technical Specifications & Schedule of Requirements",
            "mandatory": True,
            "status": "awaiting_review",
            "suggested_doc_type": "technical_compliance"
        })

        # 7. Financial Turnover Criteria
        turnover_match = re.search(r'(?:Minimum\s+Average\s+Annual\s+Turnover|Turnover\s+Criteria)[^\n\r]*', text, re.IGNORECASE)
        t_desc = turnover_match.group(0) if turnover_match else "Certified annual financial turnover of bidder for last 3 financial years attested by Chartered Accountant with UDIN."
        requirements.append({
            "req_type": "financial",
            "title": "Financial Turnover & CA Certificate",
            "description": t_desc,
            "source_doc": primary_doc,
            "source_page_section": "Eligibility Criteria - Financial Standing",
            "mandatory": True,
            "status": "awaiting_review",
            "suggested_doc_type": "turnover_certificate"
        })

        # 8. Past Experience / Performance
        exp_match = re.search(r'(?:Past\s+Performance|Experience\s+Criteria)[^\n\r]*', text, re.IGNORECASE)
        exp_desc = exp_match.group(0) if exp_match else "Proof of past experience delivering similar goods/services with copies of contracts/work orders and completion certificates."
        requirements.append({
            "req_type": "eligibility",
            "title": "Past Experience & Performance Track Record",
            "description": exp_desc,
            "source_doc": primary_doc,
            "source_page_section": "Experience Criteria",
            "mandatory": True,
            "status": "awaiting_review",
            "suggested_doc_type": "past_experience"
        })

        # 9. OEM Authorization (MAF) if mentioned
        if "oem" in text.lower() or "authorization" in text.lower() or "manufacturer authorization" in text.lower():
            requirements.append({
                "req_type": "technical",
                "title": "Manufacturer's Authorization Form (MAF)",
                "description": "OEM authorization in tender format certifying bidder as authorized distributor/system integrator with warranty backing.",
                "source_doc": atc_doc,
                "source_page_section": "OEM Authorization Clause",
                "mandatory": False,
                "status": "awaiting_review",
                "suggested_doc_type": "oem_authorization"
            })

        # 10. Company Profile & Registration Documents
        requirements.append({
            "req_type": "statutory",
            "title": "Company Profile & Statutory Registrations",
            "description": "Bidder profile including GSTIN, PAN, CIN, MSME/Udyam, registered office address, and contact details of authorized signatory.",
            "source_doc": primary_doc,
            "source_page_section": "Bidder Documentation",
            "mandatory": True,
            "status": "awaiting_review",
            "suggested_doc_type": "company_profile"
        })

        return requirements

    @classmethod
    def _extract_requirements_with_ai(cls, tender_corpus: str, metadata: Dict, api_key: str) -> List[Dict[str, Any]]:
        """Uses OpenAI API with structured JSON output for deep tender clause analysis."""
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        prompt = f"""
You are an expert Government e-Marketplace (GeM) & public procurement tender analyst.
Analyze the following tender documentation and extract the complete requirement checklist of EVERY document, declaration, undertaking, technical statement, and certificate required from the bidder.

Tender Metadata:
- Tender Number: {metadata.get('tender_number')}
- Buyer: {metadata.get('buyer_name')}

Rules:
1. Map every requirement to its exact source document and section/page.
2. Clearly distinguish mandatory vs conditional requirements.
3. Classify suggested_doc_type as one of:
   - covering_letter
   - non_blacklisting
   - technical_compliance
   - undertaking
   - eligibility_declaration
   - turnover_certificate
   - past_experience
   - oem_authorization
   - company_profile
   - boq_commercial
   - other

Output JSON format ONLY:
{{
  "requirements": [
    {{
      "req_type": "declaration|financial|technical|eligibility|statutory",
      "title": "Short title",
      "description": "Precise requirement wording from tender",
      "source_doc": "filename of source",
      "source_page_section": "Page or Clause number",
      "mandatory": true,
      "suggested_doc_type": "matching category"
    }}
  ]
}}

Tender Text (First 25,000 chars):
{tender_corpus[:25000]}
"""
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a senior GeM tender compliance officer. Extract all mandatory tender bid documents with exact source citations."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        reqs = parsed.get("requirements", [])
        if not reqs:
            raise ValueError("Empty requirements returned from AI")

        for r in reqs:
            r["status"] = "awaiting_review"

        return reqs
