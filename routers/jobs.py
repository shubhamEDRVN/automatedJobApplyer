from fastapi import APIRouter
from typing import List, Dict, Any
from database import get_db

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("", response_model=List[Dict[str, Any]])
async def get_jobs():
    """
    Returns all jobs.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM jobs ORDER BY fetched_at DESC")
    jobs = [dict(r) for r in c.fetchall()]
    conn.close()
    return jobs
