"""
AI Tender Document Preparation Agent - Streamlit Application
A clean, professional application for analyzing GeM tenders, matching company templates,
generating compliant bid documents, and auditing requirements.
"""
import streamlit as st
import io
import zipfile
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from config import OPENAI_API_KEY, PROJECTS_DIR, TEMPLATES_DIR, HISTORICAL_DIR
from database import (
    get_company_facts,
    set_company_fact,
    list_company_documents,
    update_company_document_status,
    delete_company_document,
    create_tender_project,
    get_tender_project,
    list_tender_projects,
    list_tender_files,
    list_generated_documents,
    update_generated_document_status,
    list_missing_information,
    resolve_missing_information,
    list_tender_requirements
)
from company.profile_manager import CompanyProfileManager
from company.template_library import TemplateLibrary, DOCUMENT_CATEGORIES
from company.style_analyzer import StyleAnalyzer
from tender.analyzer import TenderAnalyzer
from tender.requirement_matrix import RequirementMatrix
from generation.document_builder import DocumentBuilder
from verification.compliance_checker import ComplianceChecker
from parsers.document_extractor import DocumentExtractor

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="TenderAI - Bid Document Preparation Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Corporate CSS for high-end look
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Header branding */
    .brand-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 24px 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    .brand-header h1 {
        color: #ffffff !important;
        font-size: 26px;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .brand-header p {
        color: #e0e8f0;
        font-size: 14px;
        margin-bottom: 0px;
    }
    
    /* Metric & Card styling */
    .metric-card {
        background: #ffffff;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }
    
    /* Badges */
    .badge-approved {
        background-color: #d1fae5;
        color: #065f46;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-reference {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-draft {
        background-color: #e0f2fe;
        color: #0369a1;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-warning {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }

    /* Buttons */
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR: SETTINGS & PROJECT SELECTOR -----------------
with st.sidebar:
    st.markdown("### ⚙️ System Configuration")
    api_key_input = st.text_input(
        "OpenAI API Key",
        value=OPENAI_API_KEY,
        type="password",
        help="Reads from .env by default. Enter your OpenAI API Key for advanced AI drafting and clause extraction."
    )
    if api_key_input:
        st.caption("🟢 OpenAI API Key configured")
    else:
        st.caption("🟡 No key provided. System uses deterministic statutory generator.")

    st.divider()

    # Project Management
    st.markdown("### 📁 Tender Projects")
    projects = list_tender_projects()
    
    project_names = [f"#{p['id']} - {p['name']}" for p in projects]
    if "selected_project_idx" not in st.session_state:
        st.session_state.selected_project_idx = 0

    if projects:
        chosen_proj_str = st.selectbox(
            "Select Active Tender",
            project_names,
            index=min(st.session_state.selected_project_idx, len(projects)-1)
        )
        selected_project_id = int(chosen_proj_str.split(" - ")[0].replace("#", ""))
    else:
        selected_project_id = None
        st.info("No tender projects created yet. Create one below.")

    with st.expander("➕ Create New Tender Project"):
        new_proj_name = st.text_input("Project Name", placeholder="e.g. GeM AI Server Bid 2024")
        if st.button("Create Project", use_container_width=True):
            if new_proj_name.strip():
                pid = TenderAnalyzer.create_project(new_proj_name.strip())
                st.success(f"Created Project #{pid}")
                st.session_state.selected_project_idx = 0
                st.rerun()
            else:
                st.error("Please enter a project name.")

    st.divider()
    st.markdown("### 🛡️ Core Rules")
    st.markdown("""
    - **Never invent facts**: Registration numbers, GST, PAN, turnover & certificates are strictly checked.
    - **Template fidelity**: Preserves headers, letterheads, margins, and signature blocks.
    - **Human Approval**: You must inspect and approve every draft before downloading.
    """)

# ----------------- BRAND BANNER -----------------
st.markdown("""
<div class="brand-header">
    <h1>📄 Tender AI Document Preparation Agent</h1>
    <p>Automated analysis of GeM tender packages, corporate template matching, AI-assisted drafting, and statutory compliance auditing.</p>
</div>
""", unsafe_allow_html=True)

# ----------------- MAIN NAVIGATION TABS -----------------
tab_upload, tab_company, tab_review = st.tabs([
    "1️⃣ Upload Tender Package",
    "2️⃣ Company Library & Templates",
    "3️⃣ Review, Verify & Download"
])

# =========================================================================
# TAB 1: UPLOAD TENDER
# =========================================================================
with tab_upload:
    st.subheader("A. Upload Tender Documentation")
    st.markdown(
        "Upload the complete tender package from GeM or public procurement portal. "
        "Includes the **Bid Document**, **Buyer Added Bid Specific ATC**, **Technical Specifications**, "
        "**BOQ / Price Schedules**, **Annexures**, and **Corrigenda**."
    )

    if not selected_project_id:
        st.warning("Please create or select a Tender Project from the sidebar first.")
    else:
        current_project = get_tender_project(selected_project_id)
        st.info(f"**Active Tender Project:** #{current_project['id']} — **{current_project['name']}**")

        # Multi-file uploader
        uploaded_files = st.file_uploader(
            "Upload tender package files (PDF, DOCX, DOC, XLSX, XLS, TXT)",
            type=["pdf", "docx", "doc", "xlsx", "xls", "txt"],
            accept_multiple_files=True,
            help="Select one or more files from your tender package."
        )

        if uploaded_files:
            if st.button("📥 Save & Ingest Uploaded Files", use_container_width=True):
                ingest_count = 0
                progress_bar = st.progress(0)
                temp_dir = PROJECTS_DIR / str(selected_project_id) / "input"
                temp_dir.mkdir(parents=True, exist_ok=True)

                for i, file_obj in enumerate(uploaded_files):
                    file_path = temp_dir / file_obj.name
                    with open(file_path, "wb") as f:
                        f.write(file_obj.getbuffer())

                    TenderAnalyzer.ingest_tender_file(selected_project_id, file_path, filename=file_obj.name)
                    ingest_count += 1
                    progress_bar.progress((i + 1) / len(uploaded_files))

                st.success(f"Successfully ingested {ingest_count} tender file(s).")
                st.rerun()

        # Display currently ingested files
        existing_files = list_tender_files(selected_project_id)
        if existing_files:
            st.markdown("#### Ingested Tender Files")
            file_table = []
            for f in existing_files:
                err_badge = f"⚠️ {f['error_message']}" if f.get("error_message") else "✅ Readable"
                file_table.append({
                    "Filename": f["filename"],
                    "Category": f["category"].upper(),
                    "Pages": f["page_count"],
                    "Status": err_badge
                })
            st.dataframe(file_table, use_container_width=True)

            st.divider()

            # SINGLE ACTION BUTTON
            st.markdown("### 🚀 Execute Analysis & Document Preparation")
            col_btn, col_info = st.columns([1, 2])
            with col_btn:
                run_btn = st.button("⚡ Analyze Tender & Prepare Documents", type="primary", use_container_width=True)

            with col_info:
                st.caption(
                    "This reads all tender files, extracts metadata and corrigenda, "
                    "maps statutory requirements, matches your approved company templates, "
                    "drafts editable DOCX/XLSX documents, and runs a compliance verification audit."
                )

            if run_btn:
                with st.spinner("Analyzing tender package, reading ATC clauses, and drafting bid documents..."):
                    try:
                        # 1. Analyze tender package
                        analysis_result = TenderAnalyzer.analyze_tender_package(
                            project_id=selected_project_id,
                            api_key=api_key_input
                        )
                        meta = analysis_result.get("metadata", {})

                        st.success(f"Tender Analyzed: {meta.get('tender_number')} | Buyer: {meta.get('buyer_name')}")
                        if analysis_result.get("extraction_warnings"):
                            for w in analysis_result["extraction_warnings"]:
                                st.warning(w)

                        # 2. Build all applicable bid documents
                        prep_docs = DocumentBuilder.prepare_all_documents(
                            project_id=selected_project_id,
                            api_key=api_key_input
                        )
                        st.success(f"Generated {len(prep_docs)} editable bid document draft(s).")

                        # 3. Run compliance verification
                        audit = ComplianceChecker.run_compliance_audit(selected_project_id)
                        st.info(f"Compliance Audit Complete: {audit['addressed_and_supported']} addressed, {audit['awaiting_human_review']} awaiting review.")

                        st.balloons()
                        st.success("Analysis and drafting complete! Navigate to the 'Review, Verify & Download' tab to inspect results.")

                    except Exception as ex:
                        st.error(f"Error during processing: {str(ex)}")

        else:
            st.info("No tender files uploaded yet for this project. Upload files above to get started.")

# =========================================================================
# TAB 2: COMPANY DOCUMENTS & TEMPLATES
# =========================================================================
with tab_company:
    st.subheader("B. My Company Documents & Reusable Template Library")
    st.markdown(
        "Upload your company's official templates, past successful tender submissions, "
        "and standard declarations. The AI learns your letterhead, formatting, fonts, margins, "
        "and formal tone to match them precisely."
    )

    col_upload_tpl, col_profile_facts = st.columns([1.1, 0.9])

    with col_upload_tpl:
        st.markdown("#### 📤 Upload Company Document / Template")
        doc_type_choice = st.radio(
            "Document Type",
            ["Official Word/Excel Template", "Previous Tender Submission / Approved Example"],
            horizontal=True
        )
        is_template = (doc_type_choice == "Official Word/Excel Template")

        tpl_file = st.file_uploader(
            "Select Document (DOCX, XLSX, PDF)",
            type=["docx", "xlsx", "pdf", "txt"],
            key="company_doc_uploader"
        )

        col_cat, col_status = st.columns(2)
        with col_cat:
            cat_options = [c[0] for c in DOCUMENT_CATEGORIES]
            cat_labels = {c[0]: c[1] for c in DOCUMENT_CATEGORIES}
            chosen_category = st.selectbox(
                "Document Category",
                cat_options,
                format_func=lambda x: cat_labels.get(x, x)
            )

        with col_status:
            is_approved = st.checkbox("Mark as Approved Example", value=True, help="Uncheck if outdated or reference only.")

        doc_title = st.text_input("Document Label / Title", placeholder="e.g. Standard Letterhead Template 2024")

        if tpl_file and st.button("Save to Template Library"):
            save_dest = (TEMPLATES_DIR if is_template else HISTORICAL_DIR) / tpl_file.name
            with open(save_dest, "wb") as f:
                f.write(tpl_file.getbuffer())

            doc_id = TemplateLibrary.register_document(
                file_source_path=save_dest,
                is_template=is_template,
                is_approved=is_approved,
                category_override=chosen_category,
                title=doc_title
            )

            # Extract facts from text if applicable
            extracted = DocumentExtractor.extract(save_dest)
            auto_facts = CompanyProfileManager.extract_facts_from_text(extracted.get("text", ""))
            if auto_facts:
                for k, v in auto_facts.items():
                    CompanyProfileManager.set_fact(k, v, category="auto_detected", is_verified=True)
                st.info(f"Auto-extracted {len(auto_facts)} company identifiers (GSTIN/PAN/Email) from document.")

            st.success(f"Document saved to library (ID #{doc_id}).")
            st.rerun()

    with col_profile_facts:
        st.markdown("#### 🏢 Verified Company Profile & Credentials")
        st.caption("Facts stored here are used during document generation. Missing facts will be marked as [REQUIRES CONFIRMATION].")

        facts = CompanyProfileManager.get_all_facts()

        with st.form("company_facts_form"):
            name_val = st.text_input("Company Legal Name", value=facts.get("company_name", {}).get("value", ""))
            addr_val = st.text_area("Registered Office Address", value=facts.get("registered_office", {}).get("value", ""), height=70)

            c1, c2 = st.columns(2)
            with c1:
                gstin_val = st.text_input("GSTIN", value=facts.get("gstin", {}).get("value", ""))
                cin_val = st.text_input("CIN", value=facts.get("cin", {}).get("value", ""))
                sig_name = st.text_input("Signatory Name", value=facts.get("authorized_signatory_name", {}).get("value", ""))
            with c2:
                pan_val = st.text_input("PAN", value=facts.get("pan", {}).get("value", ""))
                udyam_val = st.text_input("MSME / Udyam", value=facts.get("msme_udyam_number", {}).get("value", ""))
                sig_desig = st.text_input("Signatory Designation", value=facts.get("authorized_signatory_designation", {}).get("value", ""))

            turnover_val = st.text_input("Average Annual Turnover (e.g. ₹ 250.00 Lakhs)", value=facts.get("annual_turnover_fy1", {}).get("value", ""))

            if st.form_submit_button("Update Verified Profile Facts"):
                CompanyProfileManager.set_fact("company_name", name_val, "general")
                CompanyProfileManager.set_fact("registered_office", addr_val, "general")
                CompanyProfileManager.set_fact("gstin", gstin_val, "taxation")
                CompanyProfileManager.set_fact("pan", pan_val, "taxation")
                CompanyProfileManager.set_fact("cin", cin_val, "statutory")
                CompanyProfileManager.set_fact("msme_udyam_number", udyam_val, "statutory")
                CompanyProfileManager.set_fact("authorized_signatory_name", sig_name, "signatory")
                CompanyProfileManager.set_fact("authorized_signatory_designation", sig_desig, "signatory")
                CompanyProfileManager.set_fact("annual_turnover_fy1", turnover_val, "financial")
                st.success("Company facts updated successfully.")
                st.rerun()

    st.divider()

    # Style Profile & Detected Writing Patterns
    st.markdown("#### 🎨 Synthesized Company Writing & Formatting Profile")
    style = StyleAnalyzer.synthesize_style_profile()

    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.metric("Documents Analyzed", style["doc_count_analyzed"])
    with sc2:
        st.metric("Primary Font", style["primary_font"])
    with sc3:
        st.metric("Letterhead Header", "Detected" if style["letterhead_detected"] else "Standard Banner")
    with sc4:
        st.metric("Recurring Formal Phrases", len(style["recurring_formal_phrases"]))

    with st.expander("View Standard Signature Block Format"):
        st.code(style["signature_block_style"], language="text")

    st.divider()

    # Catalog of registered documents
    st.markdown("#### 📚 Document & Template Library Catalog")
    all_docs = list_company_documents()
    if all_docs:
        for doc in all_docs:
            meta = json.loads(doc.get("structure_metadata") or "{}")
            is_tpl = meta.get("is_template", False)
            badge = "🟢 Approved Example" if doc["is_approved"] else "🟡 Outdated / Reference Only"
            type_tag = "TEMPLATE" if is_tpl else "HISTORICAL"

            with st.container():
                dcol1, dcol2, dcol3, dcol4 = st.columns([3, 2, 2, 2])
                with dcol1:
                    st.write(f"**{doc['title']}** (`{doc['filename']}`)")
                    st.caption(f"Category: {doc['category'].upper()} | Type: {type_tag}")
                with dcol2:
                    st.write(badge)
                with dcol3:
                    new_state = st.toggle("Approved", value=bool(doc["is_approved"]), key=f"appr_{doc['id']}")
                    if new_state != bool(doc["is_approved"]):
                        update_company_document_status(doc["id"], 1 if new_state else 0)
                        st.rerun()
                with dcol4:
                    if st.button("🗑️ Delete", key=f"del_{doc['id']}"):
                        delete_company_document(doc["id"])
                        st.rerun()
                st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)
    else:
        st.info("No templates or previous submissions added yet. Upload documents above to train the agent on your style.")

# =========================================================================
# TAB 3: REVIEW, VERIFY & DOWNLOAD
# =========================================================================
with tab_review:
    st.subheader("C. Review, Verification & Package Download")

    if not selected_project_id:
        st.warning("Please select an active Tender Project.")
    else:
        project = get_tender_project(selected_project_id)
        gen_docs = list_generated_documents(selected_project_id)
        requirements = list_tender_requirements(selected_project_id)
        missing_items = list_missing_information(selected_project_id)

        # Overview Metrics
        m1, m2, m3, m4 = st.columns(4)
        approved_count = sum(1 for d in gen_docs if d.get("status") == "approved")
        pending_placeholders_count = sum(1 for item in missing_items if item.get("status") == "pending")

        with m1:
            st.metric("Generated Drafts", len(gen_docs))
        with m2:
            st.metric("Tender Requirements", len(requirements))
        with m3:
            st.metric("Approved by You", f"{approved_count} / {len(gen_docs)}")
        with m4:
            st.metric("Missing Info Items", pending_placeholders_count, delta=-pending_placeholders_count if pending_placeholders_count > 0 else 0, delta_color="inverse")

        st.divider()

        # ----------------- SECTION: MISSING INFORMATION RESOLVER -----------------
        if missing_items:
            with st.expander(f"⚠️ Missing Information & Confirmation Items ({pending_placeholders_count} Pending)", expanded=(pending_placeholders_count > 0)):
                st.markdown(
                    "The AI strictly refrains from fabricating data. Provide missing values below to update the verification matrix."
                )
                for item in missing_items:
                    status_icon = "🟢" if item["status"] == "provided" else "🔴"
                    icol1, icol2, icol3 = st.columns([3, 3, 2])
                    with icol1:
                        st.markdown(f"**{status_icon} {item['placeholder_key']}**")
                        st.caption(f"In: {', '.join(item.get('target_docs', []))}")
                    with icol2:
                        val_input = st.text_input(
                            "Provide Verified Value",
                            value=item.get("resolved_value") or "",
                            key=f"missing_{item['id']}",
                            placeholder="Enter verified fact or certificate number"
                        )
                    with icol3:
                        if st.button("Confirm Fact", key=f"btn_res_{item['id']}"):
                            resolve_missing_information(item["id"], val_input)
                            st.success("Fact recorded.")
                            st.rerun()

        # ----------------- SECTION: REQUIREMENT FULFILLMENT MATRIX -----------------
        if requirements:
            with st.expander("📋 Tender Requirement Fulfillment Matrix (Source Citations)", expanded=False):
                req_table = []
                for r in requirements:
                    req_table.append({
                        "ID": r["id"],
                        "Requirement Title": r["title"],
                        "Category": r["req_type"].upper(),
                        "Source Document": r["source_doc"],
                        "Section / Page": r["source_page_section"],
                        "Mandatory": "Yes" if r["mandatory"] else "No",
                        "Compliance Status": r["status"].upper()
                    })
                st.dataframe(req_table, use_container_width=True)

        st.divider()

        # ----------------- SECTION: GENERATED BID DOCUMENTS -----------------
        st.markdown("### 📄 Generated Bid Documents")
        if not gen_docs:
            st.info("No documents generated yet. Upload tender files in Tab 1 and click 'Analyze Tender & Prepare Documents'.")
        else:
            for d in gen_docs:
                doc_path = Path(d["filepath"])
                file_exists = doc_path.exists()
                status = d.get("status", "draft")

                status_badge = (
                    "🟢 Approved" if status == "approved"
                    else "🟠 Corrections Requested" if status == "corrections_requested"
                    else "🔵 Draft - Awaiting Review"
                )

                with st.container():
                    col_info, col_actions = st.columns([2.5, 1.5])

                    with col_info:
                        st.markdown(f"#### {d['doc_title']} ({doc_path.suffix.upper()})")
                        st.caption(f"**Template:** {d.get('template_used', 'N/A')} | **Status:** {status_badge}")
                        if d.get("verification_notes"):
                            st.caption(f"🔍 {d['verification_notes']}")

                        if d.get("missing_placeholders"):
                            st.markdown(f"⚠️ **Items Needing Attention:**")
                            for ph in d["missing_placeholders"]:
                                st.markdown(f"- `{ph}`")

                    with col_actions:
                        # Download single file button
                        if file_exists:
                            with open(doc_path, "rb") as f_data:
                                st.download_button(
                                    f"⬇️ Download {doc_path.name}",
                                    data=f_data.read(),
                                    file_name=doc_path.name,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if doc_path.suffix == ".docx" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"dl_{d['id']}",
                                    use_container_width=True
                                )

                        # Approval / Correction Buttons
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("✅ Approve", key=f"app_{d['id']}", use_container_width=True):
                                update_generated_document_status(d["id"], "approved")
                                st.rerun()
                        with b2:
                            if st.button("✏️ Needs Edit", key=f"cor_{d['id']}", use_container_width=True):
                                update_generated_document_status(d["id"], "corrections_requested")
                                st.rerun()

                    # Preview Document Text
                    with st.expander(f"👁️ Preview Content of {doc_path.name}"):
                        if file_exists:
                            preview_data = DocumentExtractor.extract(doc_path)
                            st.text_area(
                                "Document Content",
                                value=preview_data.get("text", "")[:4000],
                                height=200,
                                key=f"prev_{d['id']}",
                                disabled=True
                            )
                        else:
                            st.warning("File not found on disk.")

                    st.markdown("<hr style='margin: 16px 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

            st.divider()

            # ----------------- SECTION: ZIP PACKAGE EXPORT -----------------
            st.markdown("### 📦 Download Complete Bid Submission Package")
            st.caption("Bundles all generated documents and the statutory compliance checklist into a clean ZIP archive for your GeM portal submission.")

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for d in gen_docs:
                    p = Path(d["filepath"])
                    if p.exists():
                        zip_file.write(p, arcname=p.name)

                # Include a structured Compliance Checklist text file
                checklist_content = f"TENDER COMPLIANCE CHECKLIST REPORT\n"
                checklist_content += f"===================================\n"
                checklist_content += f"Tender Number: {project.get('tender_number')}\n"
                checklist_content += f"Buyer: {project.get('buyer_name')}\n"
                checklist_content += f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                checklist_content += f"REQUIREMENTS & FULFILLMENT STATUS:\n"
                for r in requirements:
                    checklist_content += f"- [{r['status'].upper()}] {r['title']} (Source: {r['source_doc']}, {r['source_page_section']})\n"
                checklist_content += f"\nDISCLAIMER: Human verification of all declarations and figures is mandatory before final submission.\n"

                zip_file.writestr("00_TENDER_COMPLIANCE_CHECKLIST.txt", checklist_content)

            zip_buffer.seek(0)
            tender_slug = (project.get("tender_number") or "tender").replace("/", "_")
            zip_filename = f"Bid_Package_{tender_slug}.zip"

            st.download_button(
                label=f"📦 Download Complete Bid Package ({zip_filename})",
                data=zip_buffer.getvalue(),
                file_name=zip_filename,
                mime="application/zip",
                type="primary",
                use_container_width=True
            )
