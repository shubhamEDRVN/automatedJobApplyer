### File: ai/matcher.py
import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from ai.prompts import MATCHER_SYSTEM_PROMPT, MATCHER_USER_PROMPT
from ai.llm_router import get_llm_router
from database import get_db

logger = logging.getLogger(__name__)

async def score_single_job(job: dict, profile_summary: dict, router) -> dict: # NEW
    """Score one job against profile. Returns full AI result dict with score, reasons, matched_skills, cover_angle."""
    job_summary = {
        "title": job["title"],
        "company": job["company"],
        "location": job.get("location", ""),
        "source": job.get("source", ""),
        "description": (job.get("description") or "")[:2500]
    }
    
    formatted_prompt = MATCHER_USER_PROMPT.format(
        profile_json=json.dumps(profile_summary),
        job_json=json.dumps(job_summary)
    )
    
    try:
        result_text = await router.generate(
            system_prompt=MATCHER_SYSTEM_PROMPT,
            user_prompt=formatted_prompt,
            json_mode=True
        )
        result = json.loads(result_text)
        
        # Validate score
        score = result.get("score", 0)
        if not isinstance(score, int):
            try:
                score = int(score)
            except ValueError:
                score = 0
        score = max(0, min(100, score))
        result["score"] = score
        return result
        
    except Exception as e:
        logger.error(f"Parse failed for job '{job['title']}': {e}")
        return {"score": 0, "reasons": ["Parse failed"], "matched_skills": [], "cover_angle": ""}

async def match_jobs(profile_id: str, min_match_score: int = 65) -> list[dict]: # CHANGED
    """Score all new jobs for this profile using the LLM router. Returns matched jobs sorted by score."""
    conn = get_db()
    c = conn.cursor()

    # Step 1 — Fetch profile with profile_id filter
    c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,))
    p_row = c.fetchone()
    if not p_row:
        logger.error(f"Profile {profile_id} not found.")
        conn.close()
        return []
    profile = dict(p_row)
    
    c.execute("SELECT * FROM skills WHERE profile_id=?", (profile_id,))
    skills = [dict(s) for s in c.fetchall()]
    
    c.execute("SELECT * FROM projects WHERE profile_id=?", (profile_id,))
    projects = [dict(p) for p in c.fetchall()]
    
    c.execute("SELECT * FROM preferences WHERE profile_id=?", (profile_id,))
    pref_row = c.fetchone()
    pref = dict(pref_row) if pref_row else None
    # min_match_score is now passed as argument — no DB override needed # FIXED

    # Step 2 — Fetch ONLY this profile's new jobs
    c.execute("SELECT * FROM jobs WHERE status='new' AND profile_id=?", (profile_id,)) # FIXED
    jobs = [dict(j) for j in c.fetchall()]
    
    if not jobs:
        logger.info(f"No new jobs for profile {profile_id}")
        conn.close()
        return []

    # Step 3 — Build clean profile_summary
    profile_summary = { # CHANGED
        "name": profile["name"],
        "education": "B.Tech CS, Medicaps University, Indore (4th year, CGPA 7.7)",
        "skills": [s["skill_name"] for s in skills],
        "target_roles": json.loads(pref["roles_wanted"]) if pref and pref.get("roles_wanted") else [],
        "target_locations": json.loads(pref["locations"]) if pref and pref.get("locations") else [],
        "resume_highlights": [
            "Freelance US HVAC SaaS: MERN, JWT/RBAC, 15+ APIs, solo delivery, 99%+ uptime",
            "SevaAI: 50+ concurrent WebSocket users, Gemini + LangChain, national hackathon finalist",
            "Friday AI: Claude + Gemini + OpenAI integrated, 20+ voice commands, sub-2s response",
            "Uber Clone: 100+ concurrent sessions, real-time GPS, Socket.IO",
            "Spring Boot intern: 1000+ daily transactions, JUnit, Agile",
            "Technical Head AWS Cloud Clubs: 10+ devs, 150+ students, 3+ hackathons",
            "National hackathon finalist x4"
        ],
        "projects": [{"title": p["title"], "stack": p.get("tech_stack", ""), "description": p.get("description", "")} for p in projects[:4]]
    }

    router = get_llm_router()
    matched_jobs = []
    total_score = 0
    total_jobs = len(jobs)

    # Step 4 — Process jobs in batches of 5 with asyncio.gather
    for i in range(0, total_jobs, 5): # NEW
        chunk = jobs[i:i+5] # NEW
        results = await asyncio.gather(*[score_single_job(job, profile_summary, router) for job in chunk], return_exceptions=True) # NEW
        
        # Step 5 — For each scored job, UPDATE the DB with ALL result fields
        for job, result in zip(chunk, results): # NEW
            if isinstance(result, Exception): # NEW
                logger.error(f"Failed to score job '{job['title']}': {result}") # NEW
                continue # NEW
                
            score = result.get("score", 0)
            status = "matched" if score >= min_match_score else "rejected"
            
            c.execute("""UPDATE jobs SET
                status=?, match_score=?, match_reasons=?, matched_skills=?, cover_angle=?
                WHERE id=?""",
                (status, score, json.dumps(result.get("reasons", [])), 
                 json.dumps(result.get("matched_skills", [])),
                 result.get("cover_angle", ""), job["id"])) # CHANGED
                 
            if status == "matched":
                job["match_score"] = score # CHANGED
                job["score"] = score # Keep original score key just in case
                matched_jobs.append(job)
                
            total_score += score
            logger.info(f"Job '{job['title']}' \u2192 score {score} \u2192 {status}")

        conn.commit()
        if i + 5 < total_jobs: # NEW
            await asyncio.sleep(1) # NEW

    conn.close()

    # Step 6 — Return matched jobs sorted by score
    matched_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True) # CHANGED
    
    n_matched = len(matched_jobs)
    avg = total_score / total_jobs if total_jobs > 0 else 0
    top_title = matched_jobs[0]["title"] if matched_jobs else "None"
    top_company = matched_jobs[0]["company"] if matched_jobs else "None"
    top_score = matched_jobs[0]["match_score"] if matched_jobs else 0
    
    logger.info(f"Matched {n_matched}/{total_jobs} jobs. Avg score: {avg:.1f}. Top: {top_title} at {top_company} ({top_score})") # CHANGED

    return matched_jobs
