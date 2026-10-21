"""
Configuration settings for Tender AI Document Preparation Agent.
"""
from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR", str(BASE_DIR / "data")))
PROJECTS_DIR = DATA_DIR / "projects"
TEMPLATES_DIR = DATA_DIR / "templates"
HISTORICAL_DIR = DATA_DIR / "historical_docs"
PROFILES_DIR = DATA_DIR / "company_profiles"
DB_PATH = DATA_DIR / "tender_agent.db"

# Ensure runtime directories exist
for directory in [DATA_DIR, PROJECTS_DIR, TEMPLATES_DIR, HISTORICAL_DIR, PROFILES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    "pdf": [".pdf"],
    "docx": [".docx", ".doc"],
    "xlsx": [".xlsx", ".xls", ".csv"],
    "text": [".txt", ".md"],
}
