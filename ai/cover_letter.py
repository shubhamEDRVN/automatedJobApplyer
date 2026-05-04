### File: ai/cover_letter.py
import os
import json
import logging
import asyncio # NEW
from typing import Dict, Any, Optional
from datetime import datetime
from ai.prompts import CL_SYSTEM_PROMPT, CL_USER_PROMPT
from ai.llm_router import get_llm_router
from database import get_db, generate_id

logger = logging.getLogger(__name__)


async def generate_cover_letter(job_id: str, profile_id: str, force_regenerate: bool = False) -> str: # CHANGED
    """Generate or return cached cover letter. Uses matcher's cover_angle for better personalisation.""" # CHANGED
    conn = get_db()
    c = conn.cursor()

    try:
        # Step 1 — Cache check
        c.execute("SELECT content FROM cover_letters WHERE job_id=? AND profile_id=?", (job_id, profile_id)) # CHANGED
        row = c.fetchone() # CHANGED
        if row and not force_regenerate: # CHANGED
            logger.info(f"Returning cached cover letter for job {job_id}") # CHANGED
            return row["content"] # CHANGED

        # Step 2 — Fetch job WITH match data
        c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) # CHANGED
        j_row = c.fetchone() # CHANGED
        if not j_row: # CHANGED
            raise ValueError(f"Job {job_id} not found") # CHANGED
        job = dict(j_row) # CHANGED

        matched_skills_raw = job.get("matched_skills") or "[]" # CHANGED
        try: # CHANGED
            matched_skills = json.loads(matched_skills_raw) # CHANGED
        except: # CHANGED
            matched_skills = [] # CHANGED

        cover_angle = job.get("cover_angle") or "" # CHANGED
        match_score = job.get("match_score") or 0 # CHANGED

        if match_score == 0 or not matched_skills: # CHANGED
            logger.warning(f"Job {job_id} has no match data. Run matcher first for best results.") # CHANGED

        # Step 2.5 — Fetch ATS Tailoring Data (if available) # NEW
        c.execute("SELECT * FROM resume_tailoring WHERE job_id=? AND profile_id=?", (job_id, profile_id)) # NEW
        t_row = c.fetchone() # NEW
        ats_data = dict(t_row) if t_row else None # NEW

        # Step 3 — Fetch profile with skills AND projects
        c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)) # CHANGED
        p_row = c.fetchone() # CHANGED
        if not p_row: # CHANGED
            raise ValueError(f"Profile {profile_id} not found") # CHANGED
        profile = dict(p_row) # CHANGED

        c.execute("SELECT * FROM skills WHERE profile_id=?", (profile_id,)) # CHANGED
        skills = [dict(s) for s in c.fetchall()] # CHANGED

        c.execute("SELECT * FROM projects WHERE profile_id=?", (profile_id,)) # CHANGED
        projects = [dict(pr) for pr in c.fetchall()] # CHANGED

        # Step 4 — Select best project based on matched_skills overlap
        best_proj = None # CHANGED
        max_overlap = -1 # CHANGED

        for proj in projects: # CHANGED
            proj_stack = proj.get("tech_stack", "") # CHANGED
            proj_skills = [s.strip().lower() for s in proj_stack.split(",") if s.strip()] # CHANGED
            overlap_count = sum(1 for s in matched_skills if str(s).lower() in proj_skills) # CHANGED
            
            if overlap_count > max_overlap: # CHANGED
                max_overlap = overlap_count # CHANGED
                best_proj = proj # CHANGED

        if not best_proj and projects: # CHANGED
            best_proj = projects[-1] # CHANGED
        elif not best_proj: # CHANGED
            best_proj = {"title": "University Projects", "description": "Various academic and personal projects.", "tech_stack": "Python, Java, MERN"} # CHANGED

        # Step 5 — Build prompt using CL_USER_PROMPT template
        job_json = json.dumps({ # CHANGED
            "title": job.get("title", ""), # CHANGED
            "company": job.get("company", ""), # CHANGED
            "location": job.get("location", ""), # CHANGED
            "description": (job.get("description") or "")[:500] # CHANGED
        }) # CHANGED

        profile_json = json.dumps({ # CHANGED
            "name": profile.get("name", "Shubham Mehta"), # CHANGED
            "education": "B.Tech CS, Medicaps University, 4th year", # CHANGED
            "skills": [s["skill_name"] for s in skills[:15]], # CHANGED
            "github": profile.get("github_url", ""), # CHANGED
            "portfolio": profile.get("portfolio_url", "") # CHANGED
        }) # CHANGED

        matched_skills_str = ", ".join(matched_skills[:6]) if matched_skills else "full-stack development" # CHANGED
        cover_angle_str = cover_angle if cover_angle else f"Build impactful products with {job.get('company', 'your company')}" # CHANGED
        best_project_str = f"{best_proj.get('title', '')}: {best_proj.get('description', '')[:150]} | Stack: {best_proj.get('tech_stack', '')}" # CHANGED

        formatted_prompt = CL_USER_PROMPT.format( # CHANGED
            job_json=job_json, # CHANGED
            profile_json=profile_json, # CHANGED
            matched_skills=matched_skills_str, # CHANGED
            cover_angle=cover_angle_str # CHANGED
        ) # CHANGED
        
        # Inject best project context slightly ahead of formatted_prompt to guide the LLM
        formatted_prompt += f"\n\nSelected Best Project for this job: {best_project_str}" # NEW

        # Inject ATS Tailored Data to make cover letter highly keyword-optimised
        if ats_data: # NEW
            ats_skills = ats_data.get("ats_skills_line", "") # NEW
            ats_keywords = ats_data.get("keyword_matches", "[]") # NEW
            formatted_prompt += f"\n\nCRITICAL ATS KEYWORDS TO INCLUDE NATURALLY: {ats_keywords}" # NEW
            formatted_prompt += f"\nReordered Skills to highlight: {ats_skills}" # NEW

        # Step 6 — Call LLM router
        router = get_llm_router() # CHANGED
        letter = await router.generate(system_prompt=CL_SYSTEM_PROMPT, user_prompt=formatted_prompt, json_mode=False) # CHANGED
        letter = letter.strip() # CHANGED

        # Step 7 — Validate word count
        word_count = len(letter.split()) # CHANGED
        if word_count < 150 or word_count > 280: # CHANGED
            logger.warning(f"Cover letter word count {word_count} outside 150–280 range for job {job_id}") # CHANGED

        # Step 8 — Upsert to cover_letters table
        new_id = generate_id() # CHANGED
        c.execute("""INSERT OR REPLACE INTO cover_letters (id, job_id, profile_id, content, generated_at) 
                     VALUES (?, ?, ?, ?, ?)""", # CHANGED
                  (new_id, job_id, profile_id, letter, datetime.utcnow().isoformat())) # CHANGED
        conn.commit() # CHANGED

        logger.info(f"Cover letter generated: {word_count} words for '{job.get('title')}' at '{job.get('company')}'") # CHANGED

        # Step 9 — Return letter string
        return letter # CHANGED

    except Exception as e:
        logger.error(f"Failed to generate cover letter: {e}")
        conn.rollback()
        return "" # CHANGED
    finally:
        conn.close()


async def generate_all_pending(profile_id: str) -> dict: # NEW
    """Generate cover letters for all matched jobs that don't have one yet.""" # NEW
    conn = get_db() # NEW
    c = conn.cursor() # NEW
    
    try: # NEW
        c.execute("""SELECT id FROM jobs 
                     WHERE profile_id=? AND status='matched' 
                     AND id NOT IN (SELECT job_id FROM cover_letters WHERE profile_id=?)""", (profile_id, profile_id)) # NEW
        pending_jobs = c.fetchall() # NEW
    finally: # NEW
        conn.close() # NEW

    results = {"generated": 0, "failed": 0, "cached": 0} # NEW
    
    for row in pending_jobs: # NEW
        job_id = row["id"] # NEW
        try: # NEW
            letter = await generate_cover_letter(job_id, profile_id, force_regenerate=False) # NEW
            if letter: # NEW
                results["generated"] += 1 # NEW
            else: # NEW
                results["failed"] += 1 # NEW
        except Exception as e: # NEW
            logger.error(f"Failed to generate cover letter for pending job {job_id}: {e}") # NEW
            results["failed"] += 1 # NEW
            
        await asyncio.sleep(1) # NEW - between calls to respect rate limits
        
    logger.info(f"Cover letter batch: {results}") # NEW
    return results # NEW
