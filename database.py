"""
SQLite persistence module for projects, templates, requirements, and generated documents.
"""
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS company_profile (
        key TEXT PRIMARY KEY,
        value TEXT,
        category TEXT,
        is_verified INTEGER DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS company_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        file_type TEXT NOT NULL,
        category TEXT NOT NULL,
        is_approved INTEGER DEFAULT 1,
        title TEXT,
        description TEXT,
        extracted_text TEXT,
        structure_metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tender_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        tender_number TEXT,
        buyer_name TEXT,
        submission_deadline TEXT,
        tender_summary TEXT,
        status TEXT DEFAULT 'created',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tender_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        file_type TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        page_count INTEGER DEFAULT 0,
        extracted_text TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES tender_projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tender_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        req_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        source_doc TEXT,
        source_page_section TEXT,
        mandatory INTEGER DEFAULT 1,
        status TEXT DEFAULT 'awaiting_review',
        suggested_doc_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES tender_projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS generated_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        doc_title TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        template_used TEXT,
        filepath TEXT NOT NULL,
        status TEXT DEFAULT 'draft',
        requirement_ids TEXT,
        missing_placeholders TEXT,
        verification_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES tender_projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS missing_information (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        placeholder_key TEXT NOT NULL,
        description TEXT,
        target_docs TEXT,
        resolved_value TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES tender_projects(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()

# Company Profile Helpers
def set_company_fact(key: str, value: str, category: str = "general", is_verified: int = 1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO company_profile (key, value, category, is_verified, updated_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(key) DO UPDATE SET
        value = excluded.value,
        category = excluded.category,
        is_verified = excluded.is_verified,
        updated_at = CURRENT_TIMESTAMP
    """, (key, value, category, is_verified))
    conn.commit()
    conn.close()

def get_company_facts(category: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    if category:
        cursor.execute("SELECT key, value, category, is_verified FROM company_profile WHERE category = ?", (category,))
    else:
        cursor.execute("SELECT key, value, category, is_verified FROM company_profile")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: {"value": row["value"], "category": row["category"], "is_verified": bool(row["is_verified"])} for row in rows}

# Company Document Helpers
def add_company_document(filename: str, filepath: str, file_type: str, category: str,
                         is_approved: int = 1, title: str = "", description: str = "",
                         extracted_text: str = "", structure_metadata: Optional[Dict] = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    meta_json = json.dumps(structure_metadata or {})
    cursor.execute("""
    INSERT INTO company_documents (filename, filepath, file_type, category, is_approved, title, description, extracted_text, structure_metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (filename, filepath, file_type, category, is_approved, title or filename, description, extracted_text, meta_json))
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id

def list_company_documents(category: Optional[str] = None, approved_only: bool = False) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM company_documents WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if approved_only:
        query += " AND is_approved = 1"
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_company_document_status(doc_id: int, is_approved: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE company_documents SET is_approved = ? WHERE id = ?", (is_approved, doc_id))
    conn.commit()
    conn.close()

def delete_company_document(doc_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM company_documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

# Tender Project Helpers
def create_tender_project(name: str, tender_number: str = "", buyer_name: str = "", submission_deadline: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tender_projects (name, tender_number, buyer_name, submission_deadline, status)
    VALUES (?, ?, ?, ?, 'created')
    """, (name, tender_number, buyer_name, submission_deadline))
    pid = cursor.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_tender_project(project_id: int) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tender_projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_tender_projects() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tender_projects ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_tender_project_metadata(project_id: int, tender_number: str = "", buyer_name: str = "",
                                   submission_deadline: str = "", summary: str = "", status: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    if tender_number:
        updates.append("tender_number = ?")
        params.append(tender_number)
    if buyer_name:
        updates.append("buyer_name = ?")
        params.append(buyer_name)
    if submission_deadline:
        updates.append("submission_deadline = ?")
        params.append(submission_deadline)
    if summary:
        updates.append("tender_summary = ?")
        params.append(summary)
    if status:
        updates.append("status = ?")
        params.append(status)
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(project_id)

    cursor.execute(f"UPDATE tender_projects SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

# Tender File Helpers
def add_tender_file(project_id: int, filename: str, filepath: str, file_type: str,
                     category: str = "general", page_count: int = 0,
                     extracted_text: str = "", error_message: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tender_files (project_id, filename, filepath, file_type, category, page_count, extracted_text, error_message)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, filename, filepath, file_type, category, page_count, extracted_text, error_message))
    fid = cursor.lastrowid
    conn.commit()
    conn.close()
    return fid

def list_tender_files(project_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tender_files WHERE project_id = ? ORDER BY id ASC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Requirement Helpers
def save_tender_requirements(project_id: int, requirements: List[Dict]):
    conn = get_connection()
    cursor = conn.cursor()
    # Replace existing requirements for clean state on re-analysis
    cursor.execute("DELETE FROM tender_requirements WHERE project_id = ?", (project_id,))
    for req in requirements:
        cursor.execute("""
        INSERT INTO tender_requirements (project_id, req_type, title, description, source_doc, source_page_section, mandatory, status, suggested_doc_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id,
            req.get("req_type", "general"),
            req.get("title", ""),
            req.get("description", ""),
            req.get("source_doc", ""),
            req.get("source_page_section", ""),
            1 if req.get("mandatory", True) else 0,
            req.get("status", "awaiting_review"),
            req.get("suggested_doc_type", "")
        ))
    conn.commit()
    conn.close()

def list_tender_requirements(project_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tender_requirements WHERE project_id = ? ORDER BY mandatory DESC, id ASC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_requirement_status(req_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tender_requirements SET status = ? WHERE id = ?", (status, req_id))
    conn.commit()
    conn.close()

# Generated Document Helpers
def add_generated_document(project_id: int, doc_title: str, doc_type: str,
                           filepath: str, template_used: str = "",
                           requirement_ids: Optional[List[int]] = None,
                           missing_placeholders: Optional[List[str]] = None,
                           verification_notes: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    req_json = json.dumps(requirement_ids or [])
    placeholders_json = json.dumps(missing_placeholders or [])
    cursor.execute("""
    INSERT INTO generated_documents (project_id, doc_title, doc_type, template_used, filepath, requirement_ids, missing_placeholders, verification_notes, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft')
    """, (project_id, doc_title, doc_type, template_used, filepath, req_json, placeholders_json, verification_notes))
    gid = cursor.lastrowid
    conn.commit()
    conn.close()
    return gid

def list_generated_documents(project_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM generated_documents WHERE project_id = ? ORDER BY id ASC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["requirement_ids"] = json.loads(d["requirement_ids"]) if d.get("requirement_ids") else []
        d["missing_placeholders"] = json.loads(d["missing_placeholders"]) if d.get("missing_placeholders") else []
        results.append(d)
    return results

def update_generated_document_status(doc_id: int, status: str, verification_notes: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    if verification_notes is not None:
        cursor.execute("UPDATE generated_documents SET status = ?, verification_notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                       (status, verification_notes, doc_id))
    else:
        cursor.execute("UPDATE generated_documents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                       (status, doc_id))
    conn.commit()
    conn.close()

# Missing Information Helpers
def record_missing_information(project_id: int, placeholder_key: str, description: str, target_doc: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, target_docs FROM missing_information WHERE project_id = ? AND placeholder_key = ?
    """, (project_id, placeholder_key))
    existing = cursor.fetchone()
    if existing:
        current_docs = json.loads(existing["target_docs"] or "[]")
        if target_doc not in current_docs:
            current_docs.append(target_doc)
            cursor.execute("UPDATE missing_information SET target_docs = ? WHERE id = ?", (json.dumps(current_docs), existing["id"]))
    else:
        cursor.execute("""
        INSERT INTO missing_information (project_id, placeholder_key, description, target_docs, status)
        VALUES (?, ?, ?, ?, 'pending')
        """, (project_id, placeholder_key, description, json.dumps([target_doc])))
    conn.commit()
    conn.close()

def list_missing_information(project_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM missing_information WHERE project_id = ? ORDER BY status DESC, id ASC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["target_docs"] = json.loads(d["target_docs"]) if d.get("target_docs") else []
        results.append(d)
    return results

def resolve_missing_information(info_id: int, resolved_value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE missing_information SET resolved_value = ?, status = 'provided' WHERE id = ?",
                   (resolved_value, info_id))
    conn.commit()
    conn.close()

# Initialize DB on load
init_db()
