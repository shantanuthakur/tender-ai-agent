"""
AI Agent for retrieval-based drafting of bid documents with strict anti-hallucination controls.
"""
from typing import Dict, Any, List, Optional, Tuple
import re
import json
from config import OPENAI_API_KEY, OPENAI_MODEL
from database import list_company_documents
from company.profile_manager import CompanyProfileManager
from company.style_analyzer import StyleAnalyzer

class AIAgent:
    """Drafts tender bid documents by synthesizing company templates, verified facts, and tender requirements."""

    @classmethod
    def find_relevant_historical_context(cls, doc_type: str, requirement_desc: str) -> str:
        """
        Retrieves the most relevant excerpts from approved company documents and historical submissions.
        """
        approved_docs = list_company_documents(approved_only=True)
        if not approved_docs:
            return ""

        # Score docs by relevance
        scored_docs = []
        req_terms = set(re.findall(r'\w+', (doc_type + " " + requirement_desc).lower()))

        for doc in approved_docs:
            text = doc.get("extracted_text", "")
            title = (doc.get("title") or "").lower()
            cat = (doc.get("category") or "").lower()

            score = 0
            if cat == doc_type:
                score += 10
            for term in req_terms:
                if len(term) > 3:
                    if term in title:
                        score += 5
                    score += min(text.lower().count(term), 10)

            scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)

        # Assemble top excerpts
        top_excerpts = []
        for score, doc in scored_docs[:2]:
            if score > 0:
                snippet = doc.get("extracted_text", "")[:2500]
                top_excerpts.append(f"--- Example from Approved Document [{doc.get('title')}] ---\n{snippet}")

        return "\n\n".join(top_excerpts)

    @classmethod
    def draft_document_content(
        cls,
        doc_type: str,
        doc_title: str,
        tender_number: str,
        buyer_name: str,
        requirements: List[Dict[str, Any]],
        template_doc: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Drafts the body content for a document.
        Returns:
            (body_sections, list_of_missing_placeholders)
        """
        use_key = api_key or OPENAI_API_KEY
        req_summary = "\n".join(f"- {r.get('title')}: {r.get('description')}" for r in requirements)

        # Gather verified facts
        company_facts = CompanyProfileManager.get_all_facts()
        company_name = company_facts.get("company_name", {}).get("value") or "[REQUIRES CONFIRMATION: Company Legal Name]"
        gstin = company_facts.get("gstin", {}).get("value") or "[REQUIRES CONFIRMATION: GSTIN]"
        pan = company_facts.get("pan", {}).get("value") or "[REQUIRES CONFIRMATION: PAN]"
        cin = company_facts.get("cin", {}).get("value") or "[REQUIRES CONFIRMATION: CIN]"
        address = company_facts.get("registered_office", {}).get("value") or "[REQUIRES CONFIRMATION: Registered Office Address]"
        signatory_name = company_facts.get("authorized_signatory_name", {}).get("value") or "[REQUIRES CONFIRMATION: Authorized Signatory Name]"
        signatory_desig = company_facts.get("authorized_signatory_designation", {}).get("value") or "[REQUIRES CONFIRMATION: Signatory Designation]"
        email = company_facts.get("contact_email", {}).get("value") or "[REQUIRES CONFIRMATION: Contact Email]"
        phone = company_facts.get("contact_phone", {}).get("value") or "[REQUIRES CONFIRMATION: Contact Phone]"

        # Retrieve relevant historical writing
        historical_context = cls.find_relevant_historical_context(doc_type, req_summary)
        style_profile = StyleAnalyzer.synthesize_style_profile()

        if use_key and len(use_key.strip()) > 10:
            try:
                sections = cls._draft_with_openai(
                    doc_type=doc_type,
                    doc_title=doc_title,
                    tender_number=tender_number,
                    buyer_name=buyer_name,
                    req_summary=req_summary,
                    company_facts={
                        "company_name": company_name,
                        "gstin": gstin,
                        "pan": pan,
                        "cin": cin,
                        "address": address,
                        "signatory_name": signatory_name,
                        "signatory_desig": signatory_desig,
                        "email": email,
                        "phone": phone
                    },
                    historical_context=historical_context,
                    style_profile=style_profile,
                    api_key=use_key
                )
            except Exception as e:
                sections = cls._draft_deterministic(doc_type, doc_title, tender_number, buyer_name, company_facts)
        else:
            sections = cls._draft_deterministic(doc_type, doc_title, tender_number, buyer_name, company_facts)

        # Detect all placeholders [REQUIRES CONFIRMATION: ...]
        missing_placeholders = []
        for sec in sections:
            for p in sec.get("paragraphs", []):
                found = re.findall(r'\[REQUIRES CONFIRMATION:\s*([^\]]+)\]', p)
                for f in found:
                    cleaned = f"REQUIRES CONFIRMATION: {f.strip()}"
                    if cleaned not in missing_placeholders:
                        missing_placeholders.append(cleaned)

        return sections, missing_placeholders

    @classmethod
    def _draft_with_openai(
        cls,
        doc_type: str,
        doc_title: str,
        tender_number: str,
        buyer_name: str,
        req_summary: str,
        company_facts: Dict[str, str],
        historical_context: str,
        style_profile: Dict[str, Any],
        api_key: str
    ) -> List[Dict[str, Any]]:
        """Invokes OpenAI Chat Completion API with strict anti-fabrication prompt."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""
You are a senior GeM tender documentation specialist.
Draft the complete formal content for the tender document: "{doc_title}" (Category: {doc_type}).

Tender Details:
- Tender / Bid Number: {tender_number}
- Buyer / Procuring Entity: {buyer_name}

Tender Requirements to fulfill:
{req_summary}

Verified Company Facts:
- Company Name: {company_facts.get('company_name')}
- Registered Office: {company_facts.get('address')}
- GSTIN: {company_facts.get('gstin')}
- PAN: {company_facts.get('pan')}
- CIN: {company_facts.get('cin')}
- Authorized Signatory: {company_facts.get('signatory_name')} ({company_facts.get('signatory_desig')})
- Contact: {company_facts.get('email')}, {company_facts.get('phone')}

Approved Historical Reference Wording from Company:
{historical_context if historical_context else "None available. Use standard statutory public procurement wording."}

CRITICAL RULES (NEVER VIOLATE):
1. NEVER invent, assume, or fabricate any financial turnover figure, past contract, OEM authorization, certificate number, or date.
2. If any piece of required information is not verified in the facts above, you MUST insert a placeholder in this EXACT format:
   [REQUIRES CONFIRMATION: <Description of missing information>]
3. Match the company's formal tone, statutory phrasing, and structure.
4. Output must be structured JSON in the exact schema below.

JSON Schema:
{{
  "sections": [
    {{
      "heading": "Optional section heading or leave empty",
      "paragraphs": [
        "Paragraph text 1...",
        "Paragraph text 2..."
      ]
    }}
  ]
}}
"""
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional tender documentation agent. You NEVER fabricate company credentials and always insert [REQUIRES CONFIRMATION: ...] placeholders when data is unverified."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        sections = parsed.get("sections", [])
        if not sections:
            raise ValueError("No sections returned from OpenAI drafting")
        return sections

    @classmethod
    def _draft_deterministic(
        cls,
        doc_type: str,
        doc_title: str,
        tender_number: str,
        buyer_name: str,
        facts: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        High quality, statutory compliant deterministic document generator.
        Used as fallback or offline mode, strictly guaranteeing zero hallucinations.
        """
        c_name = facts.get("company_name", {}).get("value") or "[REQUIRES CONFIRMATION: Company Legal Name]"
        c_addr = facts.get("registered_office", {}).get("value") or "[REQUIRES CONFIRMATION: Registered Office Address]"
        c_gstin = facts.get("gstin", {}).get("value") or "[REQUIRES CONFIRMATION: GSTIN]"
        c_pan = facts.get("pan", {}).get("value") or "[REQUIRES CONFIRMATION: PAN]"
        c_cin = facts.get("cin", {}).get("value") or "[REQUIRES CONFIRMATION: CIN]"
        sig_name = facts.get("authorized_signatory_name", {}).get("value") or "[REQUIRES CONFIRMATION: Authorized Signatory Name]"
        sig_desig = facts.get("authorized_signatory_designation", {}).get("value") or "[REQUIRES CONFIRMATION: Signatory Designation]"

        if doc_type == "covering_letter":
            return [
                {
                    "heading": "To The Buyer",
                    "paragraphs": [
                        f"To,\n{buyer_name}\nGovernment e-Marketplace (GeM) / Procuring Authority",
                        f"Subject: Submission of Bid Document for Tender No: {tender_number}",
                        f"Dear Sir / Madam,",
                        f"1. With reference to the above cited Bid Number {tender_number} issued by your esteemed organization, we, M/s {c_name}, having our registered office at {c_addr}, hereby submit our unconditional and complete bid submission.",
                        f"2. We have thoroughly examined all the tender documents, terms and conditions, Buyer Added Bid Specific ATC, specifications, and corrigenda. We confirm our full acceptance of all provisions without any reservation or deviation.",
                        f"3. We confirm that all information, declarations, and certificates enclosed in our submission are true, authentic, and verifiable from relevant statutory authorities."
                    ]
                },
                {
                    "heading": "Statutory Identifiers",
                    "paragraphs": [
                        f"Our statutory credentials are as follows:\n- Bidder Name: {c_name}\n- GSTIN: {c_gstin}\n- PAN: {c_pan}\n- CIN: {c_cin}\n- Authorized Signatory: {sig_name}, {sig_desig}"
                    ]
                }
            ]

        elif doc_type == "non_blacklisting":
            return [
                {
                    "heading": "AFFIDAVIT / DECLARATION OF NON-BLACKLISTING",
                    "paragraphs": [
                        f"We, M/s {c_name}, having registered office at {c_addr}, do hereby solemnly affirm and declare on oath as under:",
                        f"1. That we have not been debarred, blacklisted, or banned by the Government e-Marketplace (GeM), Ministry of Finance, any Central/State Government Ministry, Department, Public Sector Undertaking (PSU), or autonomous body as on the date of submission of this bid.",
                        f"2. That no contract entered into by us has been terminated prematurely by any government purchaser due to default, failure, or breach of contract terms during the preceding 3 (three) financial years.",
                        f"3. That neither the bidder company nor any of its Directors/Partners have been convicted by any Court of Law for offenses involving moral turpitude or economic offenses.",
                        f"4. If this declaration is found to be false or incorrect at any stage, the Buyer / GeM Authority shall have the right to cancel our bid, forfeit the EMD/Performance Security, and initiate appropriate legal proceedings."
                    ]
                }
            ]

        elif doc_type == "undertaking":
            return [
                {
                    "heading": "UNDERTAKING FOR COMPLIANCE OF TENDER TERMS & ATC",
                    "paragraphs": [
                        f"Reference Tender / Bid No: {tender_number}\nBuyer: {buyer_name}",
                        f"We, M/s {c_name}, hereby solemnly declare and undertake that:",
                        f"1. Unconditional Acceptance: We unconditionally accept all the terms, conditions, specifications, delivery schedules, and Additional Terms and Conditions (ATC) specified in Tender No. {tender_number} including all amendments and corrigenda issued thereof.",
                        f"2. Land Border Restriction Compliance: We confirm that we have read the clause regarding restrictions on procurement from a bidder of a country which shares a land border with India (Order No. F.No.6/18/2019-PPD dated 23.07.2020 and Rule 144(xi) of GFR 2017). We certify that our company is not from such a country, or if from such a country, has been registered with the Competent Authority. [REQUIRES CONFIRMATION: Competent Authority Registration Certificate if applicable]",
                        f"3. Genuine Goods & Warranty: We undertake to provide brand new, genuine products meeting all technical specifications with comprehensive warranty backing as required by the Buyer."
                    ]
                }
            ]

        elif doc_type == "eligibility_declaration":
            return [
                {
                    "heading": "LOCAL CONTENT (MAKE IN INDIA) DECLARATION",
                    "paragraphs": [
                        f"In accordance with the Public Procurement (Preference to Make in India) Order (PPP-MII Order) issued by DPIIT:",
                        f"1. We hereby certify that the goods/services offered by M/s {c_name} for Tender No. {tender_number} meet the required local content threshold.",
                        f"2. The percentage of local content in the offered products is: [REQUIRES CONFIRMATION: Exact percentage of Local Content (e.g. 50% or above)]",
                        f"3. Classification: We classify as a [REQUIRES CONFIRMATION: Class-I Local Supplier / Class-II Local Supplier].",
                        f"4. Location of Value Addition: The location at which local value addition is carried out is: [REQUIRES CONFIRMATION: Manufacturing / Value Addition Plant Address]."
                    ]
                }
            ]

        elif doc_type == "turnover_certificate":
            turnover_1 = facts.get("annual_turnover_fy1", {}).get("value") or "[REQUIRES CONFIRMATION: Turnover for FY 2023-24 in INR Lakhs]"
            turnover_2 = facts.get("annual_turnover_fy2", {}).get("value") or "[REQUIRES CONFIRMATION: Turnover for FY 2022-23 in INR Lakhs]"
            turnover_3 = facts.get("annual_turnover_fy3", {}).get("value") or "[REQUIRES CONFIRMATION: Turnover for FY 2021-22 in INR Lakhs]"

            return [
                {
                    "heading": "ANNUAL FINANCIAL TURNOVER SUMMARY & CERTIFICATION",
                    "paragraphs": [
                        f"This is to certify that the Annual Turnover of M/s {c_name} (PAN: {c_pan}, GSTIN: {c_gstin}) for the preceding three financial years as per audited balance sheets is as follows:",
                        f"1. Financial Year 2023-24: {turnover_1}",
                        f"2. Financial Year 2022-23: {turnover_2}",
                        f"3. Financial Year 2021-22: {turnover_3}",
                        f"Average Annual Turnover: [REQUIRES CONFIRMATION: Computed 3-Year Average Turnover in INR Lakhs]",
                        f"Chartered Accountant UDIN: [REQUIRES CONFIRMATION: Unique Document Identification Number (UDIN) from CA]\nCA Membership No: [REQUIRES CONFIRMATION: CA Membership Number]\nFirm Registration No: [REQUIRES CONFIRMATION: CA Firm Registration Number]"
                    ]
                }
            ]

        elif doc_type == "past_experience":
            return [
                {
                    "heading": "STATEMENT OF PAST EXPERIENCE & PERFORMANCE",
                    "paragraphs": [
                        f"Details of similar contracts executed by M/s {c_name} for Government Departments, PSUs, or Public Entities in accordance with the tender eligibility criteria:",
                        f"Project 1: [REQUIRES CONFIRMATION: Client Name, Contract No., Value, and Completion Date]",
                        f"Project 2: [REQUIRES CONFIRMATION: Client Name, Contract No., Value, and Completion Date]",
                        f"Project 3: [REQUIRES CONFIRMATION: Client Name, Contract No., Value, and Completion Date]",
                        f"Copies of relevant Work Orders, Purchase Orders, and Satisfactory Completion / Performance Certificates are attached herewith as supporting evidence."
                    ]
                }
            ]

        elif doc_type == "technical_compliance":
            return [
                {
                    "heading": "TECHNICAL SPECIFICATION COMPLIANCE STATEMENT",
                    "paragraphs": [
                        f"Tender Reference: {tender_number} | Buyer: {buyer_name}",
                        f"We, M/s {c_name}, confirm that our offered technical solution conforms completely and unconditionally to all parameters specified in the Technical Specifications and Schedule of Requirements.",
                        f"Make & Model Offered: [REQUIRES CONFIRMATION: Offered Equipment/Product Make and Model Number]",
                        f"Technical Catalog / Datasheet Reference: [REQUIRES CONFIRMATION: OEM Datasheet / Technical Literature Document Reference]",
                        f"Deviations: NIL. The offered solution satisfies or exceeds all mandatory technical parameters."
                    ]
                }
            ]

        elif doc_type == "oem_authorization":
            return [
                {
                    "heading": "MANUFACTURER'S AUTHORIZATION FORM (MAF)",
                    "paragraphs": [
                        f"To: {buyer_name}\nReference Tender No: {tender_number}",
                        f"We, [REQUIRES CONFIRMATION: Official OEM / Manufacturer Company Name], who are proven and reputable manufacturers of [REQUIRES CONFIRMATION: Product Category / Equipment], having factories at [REQUIRES CONFIRMATION: OEM Factory Address], hereby authorize M/s {c_name} ({c_addr}) to submit a bid, negotiate, and conclude the contract with you against the above tender.",
                        f"We hereby extend our full comprehensive onsite warranty support as per tender conditions for the goods offered by the above distributor/system integrator.",
                        f"OEM Authorized Signatory: [REQUIRES CONFIRMATION: OEM Signatory Name, Designation, and Official Email]"
                    ]
                }
            ]

        else:
            return [
                {
                    "heading": doc_title.upper(),
                    "paragraphs": [
                        f"With reference to Tender No. {tender_number} issued by {buyer_name}, M/s {c_name} submits the required declaration for {doc_title}.",
                        f"We confirm compliance with all stipulations and declare that the facts submitted herein are true and verified.",
                        f"Specific Supporting Evidence / Number: [REQUIRES CONFIRMATION: Supporting reference number or certificate details]"
                    ]
                }
            ]
