import sqlite3
import uuid
import json
from datetime import datetime

DB_FILE = "internships.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # profiles
    c.execute('''CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        resume_text TEXT,
        linkedin_url TEXT,
        github_url TEXT,
        portfolio_url TEXT,
        created_at TEXT
    )''')
    # skills
    c.execute('''CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY,
        profile_id TEXT NOT NULL,
        skill_name TEXT NOT NULL,
        proficiency_level TEXT,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    # projects
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        profile_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        tech_stack TEXT,
        url TEXT,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    # preferences
    c.execute('''CREATE TABLE IF NOT EXISTS preferences (
        id TEXT PRIMARY KEY,
        profile_id TEXT UNIQUE NOT NULL,
        roles_wanted TEXT,
        locations TEXT,
        min_match_score INTEGER DEFAULT 0,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    # jobs
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT,
        description TEXT,
        apply_url TEXT,
        source TEXT,
        posted_date TEXT,
        fetched_at TEXT,
        status TEXT DEFAULT 'new',
        applied_at TEXT,
        apply_method TEXT,
        apply_status TEXT,
        UNIQUE(title, company)
    )''')
    # cover_letters
    c.execute('''CREATE TABLE IF NOT EXISTS cover_letters (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        profile_id TEXT NOT NULL,
        content TEXT NOT NULL,
        generated_at TEXT,
        UNIQUE(job_id, profile_id),
        FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )''')
    conn.commit()
    conn.close()

def generate_id():
    return str(uuid.uuid4())
