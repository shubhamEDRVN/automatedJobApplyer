import os
import sys
import argparse
import asyncio
import logging
from typing import Dict, Any

# Add parent directory to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from database import get_db, init_db
from scrapers.job_scraper import JobScraper
from scrapers.deduplicator import deduplicate_jobs
from scrapers.job_store import save_jobs
from ai.matcher import match_jobs
from ai.resume_tailor import tailor_all_matched # NEW
from ai.cover_letter import generate_cover_letter
from apply.form_filler import auto_apply
from scheduler.followup import send_followups # NEW
from scheduler.digest import send_daily_digest

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def main(dry_run: bool):
    logger.info("=== Starting Daily Job Hunt Pipeline ===")
    if dry_run:
        logger.info("MODE: DRY RUN (applications will not be submitted)")

    # Ensure DB is initialized
    init_db()
    
    conn = get_db()
    c = conn.cursor()
    
    # Fetch all active profiles
    c.execute("SELECT * FROM profiles")
    profiles = [dict(p) for p in c.fetchall()]
    
    if not profiles:
        logger.warning("No profiles found. Exiting.")
        conn.close()
        return

    # For tracking stats across all profiles
    global_stats = {"new_found": 0}
    
    for profile in profiles:
        profile_id = profile["id"]
        logger.info(f"\n=== Processing Profile: {profile.get('name')} ({profile_id}) ===")
        stats = {"new_found": 0, "matched": 0, "applied": 0}
        applied_jobs = []

        # Step 1: Run job scraper across MULTIPLE search terms
        logger.info("--- Step 1: Scraping Jobs ---")
        search_queries = [ # FIXED
            ("Full Stack Developer Intern", "remote"), # FIXED
            ("Node.js Intern", "remote"), # FIXED
            ("MERN Stack Intern", "remote"), # FIXED
            ("AI Engineer Intern", "remote"), # FIXED
            ("Backend Developer Intern", "remote") # FIXED
        ] # FIXED

        c.execute("SELECT * FROM preferences WHERE profile_id=?", (profile_id,))
        pref_row = c.fetchone()
        min_match_score = 65 # NEW
        if pref_row:
            import json
            roles = json.loads(pref_row["roles_wanted"]) if pref_row["roles_wanted"] else []
            locs = json.loads(pref_row["locations"]) if pref_row["locations"] else ["remote"]
            min_match_score = pref_row["min_match_score"] or 0 # NEW
            if roles and locs: # FIXED
                search_queries = [(role, locs[0]) for role in roles[:5]] # FIXED

        if min_match_score == 0: # NEW
            logger.warning("min_match_score is 0 — this will match ALL jobs and waste API quota.") # NEW
            logger.warning("Defaulting to 65 for this run. Set your preferences to avoid this.") # NEW
            min_match_score = 65 # FIXED

        scraper = JobScraper()
        all_raw_jobs = []
        for kw, loc in search_queries:
            logger.info(f"  Searching: '{kw}' in '{loc}'")
            batch = await scraper.run_all(kw, loc)
            all_raw_jobs.extend(batch)

        clean_jobs = deduplicate_jobs(all_raw_jobs)
        inserted_count = save_jobs(clean_jobs, profile_id=profile_id)
        stats["new_found"] = inserted_count
        global_stats["new_found"] += inserted_count
        logger.info(f"Step 1 Complete: {len(all_raw_jobs)} fetched, {len(clean_jobs)} unique, {inserted_count} new saved.")

        # Step 2: Run AI matcher
        logger.info("--- Step 2: AI Matching ---")
        matched_jobs = await match_jobs(profile_id, min_match_score=min_match_score) # FIXED
        stats["matched"] = len(matched_jobs)
        logger.info(f"Step 2 Complete: {len(matched_jobs)} jobs matched.")

        # Step 3: Generate cover letters
        logger.info("--- Step 3: Generating Cover Letters ---")
        for job in matched_jobs:
            job_id = job["id"]
            try:
                await generate_cover_letter(job_id, profile_id)
            except Exception as e:
                logger.error(f"Failed to generate cover letter for job {job_id}: {e}")
        logger.info(f"Step 3 Complete: Processed cover letters for {len(matched_jobs)} jobs.")

        # Step 3.5: ATS Resume Tailoring
        logger.info("--- Step 3.5: ATS Resume Tailoring ---") # NEW
        tailor_result = await tailor_all_matched(profile_id) # NEW
        logger.info(f"Step 3.5 Complete: {tailor_result}") # NEW

        # Step 4: Run auto-apply
        logger.info("--- Step 4: Auto-Apply ---")
        MAX_APPLICATIONS_PER_RUN = 50  # Stay under Brevo's 300/day free limit
        apply_count = 0
        for job in matched_jobs:
            job_id = job["id"]
            if dry_run:
                logger.info(f"[DRY RUN] Skipping application for job {job_id} ({job.get('title')})")
                continue

            if apply_count >= MAX_APPLICATIONS_PER_RUN:
                logger.info(f"Reached daily application limit ({MAX_APPLICATIONS_PER_RUN}). Stopping.")
                break
                
            try:
                result = await auto_apply(job_id, profile_id)
                if result.get("status") == "success":
                    stats["applied"] += 1
                    apply_count += 1
                    # Refresh job to get apply_method
                    c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
                    updated_job_row = c.fetchone()
                    if updated_job_row:
                        applied_jobs.append(dict(updated_job_row))
                    # Small delay to avoid Brevo rate limiting
                    import time
                    time.sleep(1)
                elif result.get("status") == "skipped":
                    continue
            except Exception as e:
                logger.error(f"Auto-apply failed for job {job_id}: {e}")
        logger.info(f"Step 4 Complete: Successfully applied to {stats['applied']} jobs.")

        # Step 5.5: Send 7-day follow-ups
        logger.info("--- Step 5.5: Sending 7-day follow-ups ---") # NEW
        followup_result = await send_followups(profile_id, dry_run=dry_run) # NEW
        logger.info(f"Step 5.5 Complete: {followup_result}") # NEW

        # Step 5: Send daily digest email
        logger.info("--- Step 5: Sending Daily Digest ---")
        followups_sent = followup_result.get("jobs_sent", []) # NEW
        success = send_daily_digest(profile, stats, applied_jobs, followups_sent) # CHANGED
        if success:
            logger.info("Step 5 Complete: Digest sent successfully.")
        else:
            logger.error("Step 5 Complete: Failed to send digest.")

    conn.close()
    logger.info("\n=== Daily Job Hunt Pipeline Finished ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Job Hunt Scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Run without submitting actual applications")
    args = parser.parse_args()
    
    asyncio.run(main(args.dry_run))
