# 📄 Tender AI Document Preparation Agent

An AI-powered Government e-Marketplace (GeM) and public tender document preparation system built in Python and Streamlit.

It ingests your complete tender documentation package (Bid Document, Buyer Added Specific ATC, Technical Specifications, BOQ, Annexures, Corrigenda), studies your company's existing approved documents, learns your exact writing style, layout, letterhead, and signature blocks, matches your official Word templates, drafts all applicable bid documents, tracks unverified facts with strict anti-hallucination placeholders, and generates a verified bid package for human review and approval.

---

## 🌟 Key Features

### 1. Simple, Professional Streamlit Web Interface
- **Upload Tender Package**: Multi-file uploader supporting PDF, DOCX, DOC, XLSX, XLS, and text files. Ingests bid documents, ATCs, specifications, BOQ schedules, and corrigenda.
- **Single Action Execution**: "⚡ Analyze Tender & Prepare Documents" runs the complete end-to-end pipeline with real-time feedback.
- **Company Template Library**: Upload company Word templates and past successful submissions. Mark documents as **Approved Examples** or **Reference / Outdated**.
- **Verified Facts Vault**: Store statutory registration details (GSTIN, PAN, CIN, MSME/Udyam, Authorized Signatory, Turnover, Address) with strict anti-fabrication controls.
- **Review & Approval Hub**: Preview and download individual editable DOCX/XLSX files, mark items as "Approved" or "Needs Edit", and download the complete bid package in a ZIP file.

### 2. Deep Style & Template Fidelity
- **Word Template Preservation**: Uses `python-docx` to load your official templates and substitute tender variables directly into paragraphs, headers, footers, and tables without destroying the original template layout.
- **Corporate Writing Synthesis**: Analyzes tone, phrasing, fonts, margins, letterheads, and signature blocks from your approved documents.
- **Safe Fallback**: If no approved template exists for a specific requirement, it drafts a standard GeM-compliant document and explicitly flags: `None (Proposed Standard GeM Layout - Pending Your Review)`. Original templates are never overwritten.

### 3. Strict Anti-Hallucination & Truth Enforcement
- The AI **never fabricates** registration numbers, GSTIN, PAN, turnover figures, past experience, or OEM authorizations.
- Any unverified detail is automatically replaced with an explicit placeholder:
  `[REQUIRES CONFIRMATION: <Field Name>]`
- A dedicated **Missing Information Resolver** tracks every unconfirmed item across all generated documents so you can verify or resolve them in one place.

### 4. Comprehensive Compliance Verification Matrix
- Audits every tender requirement with exact citations to source documents and page/clause numbers.
- Categorizes each requirement as:
  - `Supported` (Backed by generated document & verified company facts)
  - `Awaiting Review` (Contains pending confirmation placeholders)
  - `Missing` (Mandatory requirement with no matching submission)
  - `Not Applicable` (Conditional/optional clauses not triggered)
- **Mandatory Human Sign-off**: Automatically includes disclaimers and requires user approval before any bid submission. Never submits bids automatically.

---

## 🏗️ Architecture & Folder Structure

```
tender-ai-agent/
├── app.py                          # Streamlit Main Web Application
├── config.py                       # Configuration & path management
├── database.py                     # SQLite persistence for projects, templates, & audits
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore rules
├── parsers/                        # Document ingestion & parsing
│   ├── document_extractor.py       # Unified multi-format extractor
│   ├── pdf_parser.py               # PDF reader with scanned page detection
│   ├── docx_parser.py              # Word reader with style & structure extraction
│   └── excel_parser.py             # Excel reader for BOQ & schedules
├── company/                        # Company intelligence & profiles
│   ├── profile_manager.py          # Verified facts vault & anti-hallucination controls
│   ├── template_library.py         # Word/Excel template registry & matching engine
│   └── style_analyzer.py           # Synthesis of tone, fonts, and signature blocks
├── tender/                         # Tender analysis
│   ├── analyzer.py                 # Package analysis, ATC parser, & corrigenda tracker
│   └── requirement_matrix.py       # Checklist & source citation mapper
├── generation/                     # Drafting & document generation
│   ├── docx_generator.py           # Template-preserving DOCX builder
│   ├── excel_generator.py          # Excel technical compliance matrix generator
│   ├── ai_agent.py                 # OpenAI drafting engine with zero-hallucination fallback
│   └── document_builder.py         # Pipeline orchestrator
├── verification/                   # Post-generation compliance audit
│   └── compliance_checker.py       # Audit engine & quality control checks
├── data/                           # Application storage (local database & files)
└── tests/                          # Automated pytest suite
    ├── test_parsers.py             # Parser unit tests
    ├── test_company_profile.py     # Profile & placeholder tests
    ├── test_docx_generation.py     # DOCX & XLSX generator tests
    ├── test_tender_analyzer.py     # Tender analysis & checklist tests
    └── test_end_to_end.py          # Full workflow integration tests
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ (Tested up to Python 3.14)
- Git

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/shantanuthakur/tender-ai-agent.git
cd tender-ai-agent
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and configure your OpenAI API Key:
```bash
copy .env.example .env
```
Open `.env` in an editor and set your OpenAI API key:
```ini
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o
```
*(Note: You can also enter or update your OpenAI API Key directly in the Streamlit web sidebar at runtime).*

---

## 🖥️ Running the Application

To launch the Streamlit user interface, run:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### Recommended Workflow:
1. **Set Up Your Company Profile (Tab 2)**:
   - Enter your company name, GSTIN, PAN, registered office address, and authorized signatory details.
   - Upload any official Word templates (Letterhead, Covering Letter, Non-Blacklisting affidavit) or past successful bid documents.
   - Tag them as **Approved Examples**.
2. **Create / Select a Tender Project (Sidebar)**:
   - Click "➕ Create New Tender Project" and give it a name (e.g. `GeM Power Sector Bid`).
3. **Upload the Tender Package (Tab 1)**:
   - Upload the Bid Document, Buyer Added ATC, Specifications, and Corrigenda.
   - Click **Save & Ingest Uploaded Files**.
4. **Execute Analysis & Preparation**:
   - Click **"⚡ Analyze Tender & Prepare Documents"**.
   - The agent reads all files, incorporates corrigenda, matches your company templates, and drafts all applicable documents.
5. **Review & Audit (Tab 3)**:
   - Inspect the **Requirement Fulfillment Matrix** with exact page and clause citations.
   - Resolve any pending `[REQUIRES CONFIRMATION: ...]` items.
   - Preview each generated DOCX/XLSX file.
   - Mark documents as **Approved**.
   - Click **📦 Download Complete Bid Package** to download a ZIP containing all editable documents and a compliance checklist summary.

---

## 🧪 Running Automated Tests

Run the complete test suite using `pytest`:
```bash
pytest -v
```

All 12 unit and integration tests validate:
- Multi-format file parsing (PDF, DOCX, XLSX, TXT)
- Strict anti-hallucination placeholder insertion
- Word template preservation without overwriting
- Excel technical compliance matrix generation
- Corrigenda and deadline extension handling
- Requirement matrix mapping
- End-to-end bid drafting, verification audit, and ZIP package export

---

## 📜 Compliance & Legal Notice
This system prepares draft tender documentation for bidder convenience. Public procurement rules on GeM strictly mandate human verification of all submitted declarations, technical specifications, and statutory certificates. The bidder's authorized signatory must review, verify, sign, and seal all documents prior to portal upload.
