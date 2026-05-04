### File: scheduler/followup.py
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

from database import get_db
from apply.email_sender import send_application_email
from ai.llm_router import get_llm_router
from ai.prompts import FOLLOWUP_SYSTEM_PROMPT, FOLLOWUP_USER_PROMPT

logger = logging.getLogger(__name__)

async def send_followups(profile_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """Check for applied jobs with no response after 7 days and send follow-up emails."""
    conn = get_db()
    c = conn.cursor()
    
    results = {"sent": 0, "failed": 0, "skipped": 0, "dry_run": dry_run, "jobs_sent": []}
    
    # Step 2 — Check for follow_up_sent column
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN follow_up_sent TEXT")
        c.execute("ALTER TABLE jobs ADD COLUMN follow_up_count INTEGER DEFAULT 0")
        conn.commit()
        logger.info("Added follow_up columns to jobs table")
    except Exception:
        # Columns already exist or other error
        pass

    # Step 1 — Fetch eligible jobs
    c.execute("""
        SELECT * FROM jobs 
        WHERE profile_id=? AND status='applied' 
        AND apply_method != 'manual' 
        AND applied_at IS NOT NULL 
        AND applied_at <= datetime('now', '-7 days') 
        AND follow_up_sent IS NULL
    """, (profile_id,))
    
    eligible_jobs = [dict(row) for row in c.fetchall()]
    
    if not eligible_jobs:
        logger.info("No follow-ups due today")
        conn.close()
        return results

    # Fetch profile
    c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,))
    p_row = c.fetchone()
    if not p_row:
        logger.error(f"Profile {profile_id} not found")
        conn.close()
        return results
    profile = dict(p_row)

    router = get_llm_router()

    # Step 3 — For each eligible job
    for job in eligible_jobs:
        job_id = job["id"]
        job_title = job.get("title", "Job")
        company = job.get("company", "Company")
        applied_date = job.get("applied_at", "")[:10]
        profile_name = profile.get("name", "Applicant")
        cover_angle = job.get("cover_angle") or f"contributing to {company}"

        # Fetch cover letter
        c.execute("SELECT content FROM cover_letters WHERE job_id=? AND profile_id=?", (job_id, profile_id))
        cl_row = c.fetchone()
        
        formatted_prompt = FOLLOWUP_USER_PROMPT.format(
            job_title=job_title,
            company=company,
            applied_date=applied_date,
            profile_name=profile_name,
            cover_angle=cover_angle
        )

        try:
            followup_text = await router.generate(
                system_prompt=FOLLOWUP_SYSTEM_PROMPT, 
                user_prompt=formatted_prompt, 
                json_mode=False
            )
            followup_text = followup_text.strip()
            
            subject = f"Following up — {job_title} application ({profile_name})"
            
            if dry_run:
                logger.info(f"[DRY RUN] Would send follow-up to {company} for {job_title}")
                logger.info(f"Subject: {subject}")
                logger.info(f"Body preview: {followup_text[:200]}")
                results["skipped"] += 1
            else:
                body = followup_text + "\n\n---\n" + profile_name + " | " + profile.get("github_url", "") + " | " + profile.get("linkedin_url", "")
                success = send_application_email(
                    to_email=profile.get("email"),
                    subject=subject,
                    body=body,
                    resume_path=None
                )
                
                if success:
                    c.execute("""
                        UPDATE jobs SET follow_up_sent=datetime('now'), follow_up_count=follow_up_count+1 
                        WHERE id=?
                    """, (job_id,))
                    conn.commit()
                    results["sent"] += 1
                    results["jobs_sent"].append({"company": company, "title": job_title})
                    logger.info(f"Sent follow-up for {job_title} at {company}")
                else:
                    results["failed"] += 1
                    logger.error(f"Follow-up failed for {company}")
        except Exception as e:
            logger.error(f"Failed to generate/send follow-up for {job_id}: {e}")
            results["failed"] += 1
            
        await asyncio.sleep(2)

    conn.close()
    return results
