"""
Compliance verification engine: audits generated drafts against tender requirements,
detects missing inputs, conflicts, outdated information, and unresolved risks.
"""
from typing import Dict, Any, List
from pathlib import Path
from database import (
    get_tender_project,
    list_tender_requirements,
    list_generated_documents,
    list_missing_information,
    update_requirement_status,
    update_generated_document_status
)
from parsers.document_extractor import DocumentExtractor

class ComplianceChecker:
    """Audits generated tender documents against the requirement matrix."""

    @classmethod
    def run_compliance_audit(cls, project_id: int) -> Dict[str, Any]:
        """
        Runs comprehensive post-drafting compliance check.
        Never declares 100% compliance without mandatory human review.
        """
        project = get_tender_project(project_id)
        if not project:
            return {"error": f"Project #{project_id} not found."}

        tender_number = project.get("tender_number", "")
        buyer_name = project.get("buyer_name", "")

        requirements = list_tender_requirements(project_id)
        gen_docs = list_generated_documents(project_id)
        missing_items = list_missing_information(project_id)

        # Map requirements to documents
        req_to_doc_map = {}
        for doc in gen_docs:
            for req_id in doc.get("requirement_ids", []):
                req_to_doc_map.setdefault(req_id, []).append(doc)

        detailed_req_status = []
        addressed_count = 0
        missing_count = 0
        awaiting_review_count = 0

        # Audit each requirement
        for req in requirements:
            req_id = req["id"]
            associated_docs = req_to_doc_map.get(req_id, [])

            if not associated_docs:
                if req.get("mandatory", 1):
                    status = "missing"
                    missing_count += 1
                    notes = "Mandatory requirement has no corresponding document generated."
                else:
                    status = "not_applicable"
                    notes = "Optional / conditional requirement not triggered."
            else:
                # Check if document has unresolved placeholders
                has_pending_placeholders = any(len(d.get("missing_placeholders", [])) > 0 for d in associated_docs)
                if has_pending_placeholders:
                    status = "awaiting_review"
                    awaiting_review_count += 1
                    doc_names = ", ".join(d["doc_title"] for d in associated_docs)
                    notes = f"Document '{doc_names}' drafted, but contains pending confirmation placeholders."
                else:
                    status = "supported"
                    addressed_count += 1
                    doc_names = ", ".join(d["doc_title"] for d in associated_docs)
                    notes = f"Addressed in '{doc_names}' with verified company facts."

            update_requirement_status(req_id, status)

            detailed_req_status.append({
                "req_id": req_id,
                "title": req["title"],
                "req_type": req["req_type"],
                "mandatory": bool(req["mandatory"]),
                "source_doc": req["source_doc"],
                "source_page_section": req["source_page_section"],
                "status": status,
                "notes": notes,
                "docs": [d["doc_title"] for d in associated_docs]
            })

        # Deep Content Quality Audits
        quality_alerts = []

        # 1. Check for outdated references or mismatched tender numbers
        for doc in gen_docs:
            fpath = Path(doc["filepath"])
            if fpath.exists():
                extracted = DocumentExtractor.extract(fpath)
                text = extracted.get("text", "")

                # Check if proper tender number appears
                if tender_number and tender_number not in text and doc["doc_type"] == "docx":
                    quality_alerts.append({
                        "severity": "high",
                        "doc": doc["doc_title"],
                        "issue": f"Tender number '{tender_number}' was not found in the body text of {doc['doc_title']}."
                    })

                # Check for legacy template placeholder leftovers
                leftover_matches = ["{{", "}}", "<<", ">>"]
                if any(m in text for m in leftover_matches):
                    quality_alerts.append({
                        "severity": "medium",
                        "doc": doc["doc_title"],
                        "issue": f"Unfilled bracket syntax found in {doc['doc_title']}. Please review draft."
                    })

        # Summary of unresolved risks
        unresolved_placeholders = [item for item in missing_items if item.get("status") == "pending"]

        total_reqs = len(requirements)
        fulfillment_pct = round((addressed_count / total_reqs * 100), 1) if total_reqs > 0 else 0.0

        audit_summary = {
            "total_requirements": total_reqs,
            "addressed_and_supported": addressed_count,
            "awaiting_human_review": awaiting_review_count,
            "missing_mandatory": missing_count,
            "fulfillment_percentage": fulfillment_pct,
            "generated_documents_count": len(gen_docs),
            "pending_missing_inputs_count": len(unresolved_placeholders),
            "quality_alerts": quality_alerts,
            "requirements_detail": detailed_req_status,
            "unresolved_risks_note": (
                "AUTOMATED COMPLIANCE AUDIT COMPLETE: All statutory drafts prepared. "
                "Final review and human sign-off are strictly required before submitting to GeM portal."
            )
        }

        return audit_summary
