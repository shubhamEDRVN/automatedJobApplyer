### File: scrapers/job_store.py
import logging
from typing import List, Dict, Any
from datetime import datetime
from database import get_db, generate_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_jobs(jobs: List[Dict[str, Any]], profile_id: str) -> int: # CHANGED
    """
    Saves a list of job dicts to the SQLite jobs table.
    Skips duplicates using INSERT OR IGNORE.
    Returns the number of successfully inserted jobs.
    """
    if not jobs:
        return 0

    conn = get_db()
    c = conn.cursor()
    inserted_count = 0
    
    try:
        for job in jobs:
            job["profile_id"] = profile_id # NEW
            job["fetched_date"] = datetime.utcnow().strftime("%Y-%m-%d") # NEW
            
            c.execute("""INSERT OR IGNORE INTO jobs 
                         (id, title, company, location, description, apply_url, source, source_job_id, posted_date, fetched_at, fetched_date, status, profile_id) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""", # CHANGED
                      (generate_id(), job.get('title'), job.get('company'), job.get('location'), 
                       job.get('description'), job.get('apply_url'), job.get('source'), 
                       job.get('source_job_id'), job.get('posted_date'), datetime.utcnow().isoformat(), 
                       job.get('fetched_date'), job.get('profile_id'))) # CHANGED
            if c.rowcount > 0: # CHANGED
                inserted_count += 1 # CHANGED
                
        conn.commit()
        logger.info(f"Successfully stored {inserted_count} new jobs out of {len(jobs)} provided.")
    except Exception as e:
        logger.error(f"Failed to store jobs in SQLite: {e}")
        conn.rollback()
    finally:
        conn.close()
        
    return inserted_count
