### File: database.py
import sqlite3
import uuid
import json
from datetime import datetime
import logging

DB_FILE = "internships.db"
logger = logging.getLogger(__name__)

def get_db():
    """Returns a new SQLite connection with Row factory."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates all tables if they don't exist, then runs migration."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        phone TEXT, resume_text TEXT, linkedin_url TEXT, github_url TEXT,
        portfolio_url TEXT, created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, skill_name TEXT NOT NULL,
        proficiency_level TEXT,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, title TEXT NOT NULL,
        description TEXT, tech_stack TEXT, url TEXT,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS preferences (
        id TEXT PRIMARY KEY, profile_id TEXT UNIQUE NOT NULL,
        roles_wanted TEXT, locations TEXT,
        min_match_score INTEGER DEFAULT 65,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL,
        location TEXT, description TEXT, apply_url TEXT, source TEXT,
        source_job_id TEXT, posted_date TEXT, fetched_at TEXT, fetched_date TEXT,
        status TEXT DEFAULT 'new', applied_at TEXT, apply_method TEXT,
        apply_status TEXT, apply_error TEXT,
        profile_id TEXT NOT NULL DEFAULT 'default',
        match_score INTEGER DEFAULT NULL, match_reasons TEXT,
        matched_skills TEXT, cover_angle TEXT,
        UNIQUE(title, company, source, fetched_date)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cover_letters (
        id TEXT PRIMARY KEY, job_id TEXT NOT NULL, profile_id TEXT NOT NULL,
        content TEXT NOT NULL, generated_at TEXT,
        UNIQUE(job_id, profile_id),
        FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS resume_tailoring (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        profile_id TEXT NOT NULL,
        ats_skills_line TEXT,
        top_3_project_bullets TEXT,
        keyword_matches TEXT,
        ats_score_estimate INTEGER,
        generated_at TEXT,
        UNIQUE(job_id, profile_id)
    )''') # NEW
    conn.commit()
    conn.close()
    migrate_db()

def migrate_db():
    """Migrates existing database by adding new columns to jobs table."""
    conn = get_db()
    c = conn.cursor()
    columns_to_add = [
        "profile_id TEXT NOT NULL DEFAULT 'default'",
        "source_job_id TEXT", "fetched_date TEXT",
        "match_score INTEGER DEFAULT NULL", "match_reasons TEXT",
        "matched_skills TEXT", "cover_angle TEXT", "apply_error TEXT"
    ]
    for col_def in columns_to_add:
        col_name = col_def.split()[0]
        try:
            c.execute(f"ALTER TABLE jobs ADD COLUMN {col_def}")
            logger.info(f"Added column {col_name} to jobs table")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def generate_id() -> str:
    """Generates a new UUID4 string."""
    return str(uuid.uuid4())
