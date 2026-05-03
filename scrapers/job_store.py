import logging
from typing import List, Dict, Any
from datetime import datetime
from database import get_db, generate_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_jobs(jobs: List[Dict[str, Any]]) -> int:
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
            c.execute("SELECT id FROM jobs WHERE title=? AND company=?", (job.get('title'), job.get('company')))
            if not c.fetchone():
                c.execute("""INSERT INTO jobs 
                             (id, title, company, location, description, apply_url, source, posted_date, fetched_at, status) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (generate_id(), job.get('title'), job.get('company'), job.get('location'), 
                           job.get('description'), job.get('apply_url'), job.get('source'), 
                           job.get('posted_date'), datetime.utcnow().isoformat(), 'new'))
                inserted_count += 1
        conn.commit()
        logger.info(f"Successfully stored {inserted_count} new jobs out of {len(jobs)} provided.")
    except Exception as e:
        logger.error(f"Failed to store jobs in SQLite: {e}")
        conn.rollback()
    finally:
        conn.close()
        
    return inserted_count
