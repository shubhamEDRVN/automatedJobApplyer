### File: ai/resume_tailor.py
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

from database import get_db, generate_id
from ai.llm_router import get_llm_router

logger = logging.getLogger(__name__)

async def tailor_resume_summary(job_id: str, profile_id: str) -> dict:
    """Generate ATS-optimised resume summary tailored to a specific job. Returns dict with tailored content."""
    conn = get_db()
    c = conn.cursor()

    try:
        # Step 1 — Fetch job
        c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
        j_row = c.fetchone()
        if not j_row:
            raise ValueError(f"Job {job_id} not found.")
        job = dict(j_row)

        if job.get("status") != "matched":
            raise ValueError(f"Job {job_id} must be matched before tailoring resume.")

        title = job.get("title", "")
        company = job.get("company", "")
        description_excerpt = (job.get("description") or "")[:1500]

        try:
            matched_skills = json.loads(job.get("matched_skills") or "[]")
        except:
            matched_skills = []

        # Step 2 — Fetch profile
        c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,))
        p_row = c.fetchone()
        if not p_row:
            raise ValueError(f"Profile {profile_id} not found.")

        c.execute("SELECT skill_name FROM skills WHERE profile_id=?", (profile_id,))
        candidate_skills = [row["skill_name"] for row in c.fetchall()]

        c.execute("SELECT title, description, tech_stack FROM projects WHERE profile_id=?", (profile_id,))
        top_projects = [dict(row) for row in c.fetchall()]

        # Step 3 — Build tailor prompt
        system_prompt = """You are an expert ATS optimisation specialist. Your job is to reorder and rephrase 
a candidate's skills and project bullets to maximise keyword match with a specific job posting.
Do NOT invent skills the candidate doesn't have. Do NOT lie. Only reorder, rephrase, and emphasise.
Return ONLY valid JSON."""

        user_prompt = f"""
Candidate Skills: {json.dumps(candidate_skills)}
Top Projects: {json.dumps(top_projects)}

Job Title: {title}
Company: {company}
Matched Skills: {json.dumps(matched_skills)}
Job Description Excerpt:
{description_excerpt[:1200]}

Instruction: Return JSON with these keys:
- ats_skills_line: a single comma-separated line of skills reordered so matched_skills appear first, synonyms used where beneficial.
- top_3_project_bullets: list of exactly 3 strings, each a strong 1-sentence project bullet using keywords from the job description, with a concrete number.
- keyword_matches: list of exact keywords from the job description found in the tailored content.
- ats_score_estimate: integer 0-100 estimated ATS match score after tailoring.
"""

        # Step 4 — Call router, parse JSON, validate
        router = get_llm_router()
        response_text = await router.generate(system_prompt=system_prompt, user_prompt=user_prompt, json_mode=True)
        
        try:
            tailored_data = json.loads(response_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON for resume tailoring (job {job_id})")
            tailored_data = {
                "ats_skills_line": ", ".join(candidate_skills),
                "top_3_project_bullets": [p.get("description", "") for p in top_projects[:3]],
                "keyword_matches": matched_skills,
                "ats_score_estimate": 50
            }

        # Step 5 — Save to resume_tailoring
        new_id = generate_id()
        c.execute("""
            INSERT OR REPLACE INTO resume_tailoring 
            (id, job_id, profile_id, ats_skills_line, top_3_project_bullets, keyword_matches, ats_score_estimate, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_id,
            job_id,
            profile_id,
            tailored_data.get("ats_skills_line", ""),
            json.dumps(tailored_data.get("top_3_project_bullets", [])),
            json.dumps(tailored_data.get("keyword_matches", [])),
            tailored_data.get("ats_score_estimate", 0),
            datetime.utcnow().isoformat()
        ))
        conn.commit()

        logger.info(f"Successfully tailored resume for {title} at {company}")
        return tailored_data

    except Exception as e:
        logger.error(f"Failed to tailor resume for job {job_id}: {e}")
        conn.rollback()
        return {}
    finally:
        conn.close()


async def tailor_all_matched(profile_id: str) -> dict:
    """Run ATS tailoring for all matched jobs that haven't been tailored yet."""
    conn = get_db()
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT id FROM jobs 
            WHERE profile_id=? AND status='matched' 
            AND id NOT IN (SELECT job_id FROM resume_tailoring WHERE profile_id=?)
        """, (profile_id, profile_id))
        pending_jobs = c.fetchall()
    finally:
        conn.close()

    results = {"tailored": 0, "failed": 0}
    
    for row in pending_jobs:
        job_id = row["id"]
        try:
            tailor_data = await tailor_resume_summary(job_id, profile_id)
            if tailor_data:
                results["tailored"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            logger.error(f"Failed ATS tailoring for job {job_id}: {e}")
            results["failed"] += 1
            
        await asyncio.sleep(1)
        
    return results
