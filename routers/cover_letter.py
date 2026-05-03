from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db
from ai.cover_letter import generate_cover_letter

router = APIRouter(prefix="/cover-letter", tags=["cover-letter"])

class CoverLetterResponse(BaseModel):
    content: str
    source: str

@router.get("/{job_id}/{profile_id}", response_model=CoverLetterResponse)
async def get_or_generate_cover_letter(job_id: str, profile_id: str):
    """
    Returns the cover letter for a specific job and profile.
    If it doesn't exist, it generates one on the fly.
    """
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT content FROM cover_letters WHERE job_id=? AND profile_id=?", (job_id, profile_id))
    existing = c.fetchone()
    conn.close()

    if existing:
        return {"content": existing["content"], "source": "cache"}

    content = await generate_cover_letter(job_id, profile_id)
    if not content:
        raise HTTPException(status_code=500, detail="Failed to generate cover letter.")

    return {"content": content, "source": "generated"}
