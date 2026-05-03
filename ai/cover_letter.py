import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from ai.prompts import CL_SYSTEM_PROMPT, CL_USER_PROMPT
from ai.llm_router import get_llm_router
from database import get_db, generate_id

logger = logging.getLogger(__name__)


async def generate_cover_letter(job_id: str, profile_id: str) -> Optional[str]:
    """
    Generates a cover letter for a specific job and profile using the multi-provider LLM router.
    Saves it to the SQLite cover_letters table. Returns cached version if already exists.
    """
    conn = get_db()
    c = conn.cursor()

    # 1. Fetch Job
    c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    j_row = c.fetchone()
    if not j_row:
        logger.error(f"Job {job_id} not found.")
        conn.close()
        return None
    job = dict(j_row)

    # 2. Fetch Profile (with skills and projects)
    c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,))
    p_row = c.fetchone()
    if not p_row:
        logger.error(f"Profile {profile_id} not found.")
        conn.close()
        return None
    profile = dict(p_row)

    c.execute("SELECT * FROM skills WHERE profile_id=?", (profile_id,))
    profile['skills'] = [dict(s) for s in c.fetchall()]

    c.execute("SELECT * FROM projects WHERE profile_id=?", (profile_id,))
    profile['projects'] = [dict(pr) for pr in c.fetchall()]

    # 3. Check if already generated (cache)
    c.execute("SELECT content FROM cover_letters WHERE job_id=? AND profile_id=?", (job_id, profile_id))
    existing = c.fetchone()
    if existing:
        logger.info("Cover letter already cached. Returning existing.")
        conn.close()
        return existing['content']

    # 4. Build prompts
    profile_summary = {
        "name": profile.get("name"),
        "skills": [s.get("skill_name") for s in profile.get("skills", [])],
        "projects": [{"title": p.get("title"), "description": p.get("description")} for p in profile.get("projects", [])],
        "resume_summary": profile.get("resume_text")
    }

    job_summary = {
        "company": job.get("company"),
        "title": job.get("title"),
        "description": (job.get("description") or "")[:1500]
    }

    user_prompt = CL_USER_PROMPT.format(
        job_json=json.dumps(job_summary),
        profile_json=json.dumps(profile_summary)
    )

    # 5. Generate via multi-provider router
    try:
        router = get_llm_router()
        content = await router.generate(
            system_prompt=CL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=False
        )

        # Save to DB
        c.execute("""INSERT INTO cover_letters (id, job_id, profile_id, content, generated_at) 
                     VALUES (?, ?, ?, ?, ?)""",
                  (generate_id(), job_id, profile_id, content, datetime.utcnow().isoformat()))
        conn.commit()

        return content

    except Exception as e:
        logger.error(f"Failed to generate cover letter: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()
