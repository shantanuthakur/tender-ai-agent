# 🌟 GeM Tender AI Agent

An automated AI-powered agent to discover, analyze, and extract government tenders from the **Government e-Marketplace (GeM)** ([bidplus.gem.gov.in/all-bids](https://bidplus.gem.gov.in/all-bids)).

Specifically tailored to identify:
- **Mobile Light Towers (MST)** / Mobile Lighting Systems
- **Inflatable Light Towers** / Balloon Lighting Systems
- **Portable & LED Lighting Towers**, Floodlight Masts, and related equipment

The system uses **Selenium & Undetected ChromeDriver** to scrape live tenders, leverages **OpenAI (GPT-4o / GPT-4o-mini)** for semantic analysis, automatically generates formatted **Excel (.xlsx)** and **Word (.docx)** reports, and includes a **Modern Dark Glassmorphic Web Dashboard** to review and filter tenders.

---

## 📋 Table of Contents
1. [Key Features](#-key-features)
2. [Project Structure](#-project-structure)
3. [Prerequisites](#-prerequisites)
4. [Installation & Setup](#-installation--setup)
5. [Configuration (.env)](#-configuration-env)
6. [How to Run](#-how-to-run)
   - [Running the AI Backend Pipeline](#1-running-the-ai-backend-pipeline)
   - [Running the Frontend Dashboard](#2-running-the-frontend-dashboard)
7. [CLI Command-Line Options](#-cli-command-line-options)
8. [Generated Output Reports](#-generated-output-reports)
9. [Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 🚀 Key Features

- **Automated GeM Scraper**: Scrapes GeM Bid Plus with keyword filtering, pagination, and detail page extraction.
- **Smart AI Filtering**: Uses OpenAI to understand tender context, technical specifications, and intent (distinguishing true mobile lighting towers from stationary streetlights or generic bulbs).
- **Executive Word Report (`.docx`)**: Generates a professional tender dossier including direct links to download bid documents and technical specs.
- **Color-Coded Excel Sheet (`.xlsx`)**: Formats high, medium, and low confidence matches with key dates, estimated values, and department details.
- **Deduplication Engine**: Remembers previously discovered tenders (`tenders_log.json`) to avoid re-alerting on old tenders.
- **Interactive Web Dashboard**: Beautiful visual UI with real-time search, confidence badges, urgency counters, and JSON file importer.

---

## 📁 Project Structure

```text
tender-ai-agent/
│
├── backend/
│   ├── .env                   # Configuration & OpenAI API Key
│   ├── requirements.txt       # Python dependencies
│   ├── main.py                # Main CLI runner pipeline
│   ├── scraper.py             # GeM portal scraper (Selenium / Chrome)
│   ├── ai_filter.py           # OpenAI tender evaluation engine
│   ├── save_results.py        # Excel (.xlsx) & Word (.docx) report generator
│   └── output/                # Auto-generated reports (created upon first run)
│       ├── tenders_YYYYMMDD_HHMMSS.xlsx
│       ├── tender_report_YYYYMMDD_HHMMSS.docx
│       ├── latest_results.json
│       └── tenders_log.json
│
├── frontend/
│   ├── index.html             # Dashboard user interface
│   ├── index.css              # Glassmorphic dark styling
│   └── app.js                 # Dashboard logic & search/filter
│
└── README.md                  # Complete documentation & usage guide
```

---

## ⚙️ Prerequisites

Before getting started, ensure you have:
1. **Python 3.9 or higher** installed ([python.org](https://www.python.org/downloads/)).
   - Verify in terminal: `python --version`
2. **Google Chrome browser** installed (used by the scraper).
3. **OpenAI API Key** ([platform.openai.com/api-keys](https://platform.openai.com/api-keys)).

---

## 🛠️ Installation & Setup

### Step 1: Open Terminal / PowerShell
Navigate to the project root directory:
```powershell
cd "c:\Users\DELL\Desktop\tender ai agent"
```

### Step 2: Create and Activate a Python Virtual Environment
*(Recommended to avoid dependency conflicts)*

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

*(If PowerShell gives an execution policy warning, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### Step 3: Install Required Dependencies
```bash
cd backend
pip install -r requirements.txt
```

---

## 🔑 Configuration (.env)

Open `backend/.env` in any text editor and configure your settings:

```ini
# 1. Provide your OpenAI API Key (REQUIRED)
OPENAI_API_KEY=sk-proj-your-openai-api-key-here

# 2. OpenAI Model (Default: gpt-4o-mini is fast & cost-effective; gpt-4o is higher precision)
AI_MODEL=gpt-4o-mini

# 3. Product keywords your business provides (Used by AI evaluation)
PRODUCT_KEYWORDS=mobile lighting tower,inflatable lighting tower,MST lighting,mobile service tower,inflatable light system,balloon light,portable lighting tower,LED tower light,floodlight tower,light mast,telescopic mast light,lighting tower system,mobile solar tower

# 4. Search keywords typed into GeM's search bar (comma-separated)
SEARCH_KEYWORDS=mobile light tower,inflatable light,MST light,lighting tower,balloon light,portable light tower,LED tower light

# 5. Scraper defaults
MAX_PAGES=5
HEADLESS=true
```

---

## 🏃 How to Run

### 1. Running the AI Backend Pipeline

Make sure you are in the `backend/` directory with your virtual environment activated:

```powershell
cd "c:\Users\DELL\Desktop\tender ai agent\backend"
python main.py
```

#### What happens during execution:
1. **Portal Search**: Navigates to `bidplus.gem.gov.in/all-bids` and searches for your target keywords.
2. **Tender Extraction**: Extracts Bid Number, Items, Department, Quantity, Start Date, End Date, and Document URLs.
3. **AI Evaluation**: Sends candidate bids to OpenAI GPT to determine if they match Mobile Light Towers (MST) or Inflatable Light Systems, grading them with **HIGH**, **MEDIUM**, or **LOW** confidence + reasoning.
4. **Document Export**: Saves the filtered tenders to `backend/output/`:
   - 📊 **Excel Sheet** (`.xlsx`)
   - 📝 **Word Document** (`.docx`)
   - 💾 **JSON Data** (`latest_results.json`)

---

### 2. Running the Frontend Dashboard

You have two easy ways to view the interactive dashboard:

#### Option A: Direct Browser Launch (Easiest)
1. Open Windows File Explorer.
2. Navigate to `tender ai agent\frontend\`.
3. Double-click `index.html` (opens in Chrome, Edge, or Firefox).
4. Click **"Load File"** and choose `backend/output/latest_results.json`, or click **"Load Demo Data"** to explore the dashboard immediately.

#### Option B: Local Web Server (Supports Auto-loading Results)
From the project root:
```powershell
# Using Python built-in HTTP server:
python -m http.server 8000
```
Then open your browser at:
👉 **`http://localhost:8000/frontend/`**

*Note: Running via a local server allows the dashboard to automatically fetch and display `backend/output/latest_results.json` without having to select the file manually.*

---

## 💻 CLI Command-Line Options

You can customize the scraper behavior directly via command-line arguments:

| Option | Default | Description | Example |
|---|---|---|---|
| `--pages` | `5` | Maximum pages to scrape per keyword | `python main.py --pages 10` |
| `--headless` | `true` | Run Chrome in background (`true`) or visible window (`false`) | `python main.py --headless false` |
| `--keywords` | *(From .env)* | Custom search keywords for GeM search | `python main.py --keywords "MST,light tower"` |
| `--model` | `gpt-4o-mini` | OpenAI model to use (`gpt-4o-mini` or `gpt-4o`) | `python main.py --model gpt-4o` |
| `--no-search` | `false` | Scrapes all generic bids without typing search queries | `python main.py --no-search` |
| `--no-details`| `false` | Faster scrape: skip clicking into individual bid pages | `python main.py --no-details` |

#### Example Commands:

```powershell
# Quick test run: Scrape 2 pages with visible browser window
python main.py --pages 2 --headless false

# High-precision scan using GPT-4o for complex tenders
python main.py --pages 5 --model gpt-4o

# Targeted single keyword search
python main.py --keywords "inflatable light" --pages 3
```

---

## 📑 Generated Output Reports

All results are saved automatically inside `backend/output/`:

### 1. Excel Report (`tenders_YYYYMMDD_HHMMSS.xlsx`)
- **Summary Sheet**: Statistics, scan date, model used, and keyword criteria.
- **Tenders Sheet**: Color-coded rows (Green for High confidence, Amber for Medium, Gray for Low), direct links to GeM bid documents, specifications, and closing dates.

### 2. Word Document (`tender_report_YYYYMMDD_HHMMSS.docx`)
- Executive summary report with branded headers and layout.
- Per-tender detailed cards with AI reasoning explaining why the tender matches your requirements.
- Clickable links to download the official GeM Bid Documents.

### 3. JSON Backup (`latest_results.json`)
- Clean, structured JSON data containing all matched tenders.
- Directly loadable into the frontend dashboard or external ERP/CRM systems.

---

## ❓ Troubleshooting & FAQs

### Q: Chrome closes immediately or raises a ChromeDriver error
- Ensure you have standard Google Chrome installed. `undetected-chromedriver` automatically downloads the matching driver for your Chrome version.
- If Chrome was recently updated, close all existing Chrome processes and retry.

### Q: GeM Portal blocks or shows verification
- Run with `--headless false` so you can view the browser window:
  ```powershell
  python main.py --headless false
  ```
- The scraper uses anti-detection flags and natural delays to reduce bot detection.

### Q: "OPENAI_API_KEY is not set!"
- Check `backend/.env`. Ensure you have replaced `your-openai-api-key-here` with your valid key starting with `sk-...`.
- Make sure there are no accidental spaces or quotes around the key.

### Q: How do I schedule this to run daily?
- You can use **Windows Task Scheduler** to trigger `python main.py` automatically every morning (e.g., at 9:00 AM) to receive fresh tender reports daily.
