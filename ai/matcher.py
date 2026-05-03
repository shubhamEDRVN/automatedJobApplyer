import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from ai.prompts import MATCHER_SYSTEM_PROMPT, MATCHER_USER_PROMPT
from ai.llm_router import get_llm_router
from database import get_db

logger = logging.getLogger(__name__)


async def match_jobs(profile_id: str) -> List[Dict[str, Any]]:
    """
    Scores all 'new' jobs against a given profile using the multi-provider LLM router.
    Updates job statuses to 'matched' or 'rejected' based on the profile's min_match_score.
    Returns the list of 'matched' jobs, sorted by score descending.
    """
    conn = get_db()
    c = conn.cursor()

    # Fetch profile
    c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,))
    p_row = c.fetchone()
    if not p_row:
        logger.error(f"Profile {profile_id} not found.")
        conn.close()
        return []

    profile = dict(p_row)
    c.execute("SELECT * FROM skills WHERE profile_id=?", (profile_id,))
    profile['skills'] = [dict(s) for s in c.fetchall()]

    c.execute("SELECT * FROM preferences WHERE profile_id=?", (profile_id,))
    pref_row = c.fetchone()
    min_match_score = 0
    if pref_row:
        min_match_score = pref_row['min_match_score'] or 0
        profile['preferences'] = dict(pref_row)

    # Fetch all new jobs
    c.execute("SELECT * FROM jobs WHERE status='new'")
    jobs = [dict(j) for j in c.fetchall()]

    if not jobs:
        logger.info("No 'new' jobs to match.")
        conn.close()
        return []

    router = get_llm_router()

    profile_summary = {
        "skills": [s.get("skill_name") for s in profile.get("skills", [])],
        "resume_summary": profile.get("resume_text"),
        "preferred_roles": profile.get("preferences", {}).get("roles_wanted", [])
    }

    matched_jobs = []

    for i, job in enumerate(jobs):
        job_summary = {
            "title": job.get("title"),
            "company": job.get("company"),
            "description": (job.get("description") or "")[:2000]
        }

        user_prompt = MATCHER_USER_PROMPT.format(
            profile_json=json.dumps(profile_summary),
            job_json=json.dumps(job_summary)
        )

        try:
            result_text = await router.generate(
                system_prompt=MATCHER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True
            )
            result = json.loads(result_text)

            score = result.get("score", 0)

            if score >= min_match_score:
                status = "matched"
                job["score"] = score
                matched_jobs.append(job)
            else:
                status = "rejected"

            c.execute("UPDATE jobs SET status=? WHERE id=?", (status, job["id"]))
            logger.info(f"Job {i+1}/{len(jobs)} '{job.get('title')}' → score {score} → {status}")

            # Small delay between requests to be polite to APIs
            if i < len(jobs) - 1:
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Failed to score job '{job.get('title')}': {e}")

    conn.commit()
    conn.close()

    matched_jobs.sort(key=lambda x: x.get("score", 0), reverse=True)
    return matched_jobs
