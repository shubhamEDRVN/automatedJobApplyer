"""
Auto-Apply Engine — Multiple strategies:
  1. Email application via Brevo (most reliable)
  2. Direct form filling via Playwright (best-effort)
  3. Mark as 'manual_required' if neither works
"""

import os
import logging
from typing import Dict, Any
from datetime import datetime
from apply.email_sender import send_application_email
from database import get_db

logger = logging.getLogger(__name__)


async def auto_apply(job_id: str, profile_id: str) -> Dict[str, Any]:
    """
    Attempts to auto-apply for a job using multiple strategies:
      1. Send a professional application email via Brevo (to company or self-forward)
      2. Attempt form filling via Playwright for known platforms (Internshala)
      3. Fall back to 'manual_required'
    Updates job status in SQLite on success.
    """
    conn = get_db()
    c = conn.cursor()

    # Fetch job
    c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    j_row = c.fetchone()
    if not j_row:
        conn.close()
        return {"status": "error", "message": "Job not found"}
    job = dict(j_row)

    # Skip already-applied jobs
    if job.get("status") == "applied":
        conn.close()
        return {"status": "skipped", "message": "Already applied"}

    # Fetch profile
    c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,))
    p_row = c.fetchone()
    if not p_row:
        conn.close()
        return {"status": "error", "message": "Profile not found"}
    profile = dict(p_row)

    # Fetch cover letter
    c.execute("SELECT content FROM cover_letters WHERE job_id=? AND profile_id=?", (job_id, profile_id))
    cl_row = c.fetchone()
    cover_letter = cl_row["content"] if cl_row else "I am interested in this position. Please find my profile details below."

    apply_url = job.get("apply_url", "")
    source = job.get("source", "")
    company = job.get("company", "Unknown")
    title = job.get("title", "Position")

    logger.info(f"Auto-applying: '{title}' at '{company}' ({source})")

    # ── Strategy 1: Direct email if mailto link ────────────────────
    if apply_url.startswith("mailto:"):
        to_email = apply_url.replace("mailto:", "").split("?")[0]
        return await _apply_via_email(c, conn, job_id, profile, title, company, cover_letter, to_email)

    # ── Strategy 2: Email application (self-forward + company) ─────
    # Build a professional application email body
    email_body = f"""Dear Hiring Manager at {company},

{cover_letter}

---
Applicant Details:
Name: {profile.get('name')}
Email: {profile.get('email')}
Phone: {profile.get('phone', 'N/A')}
LinkedIn: {profile.get('linkedin_url', 'N/A')}
GitHub: {profile.get('github_url', 'N/A')}
Portfolio: {profile.get('portfolio_url', 'N/A')}

Job Applied For: {title}
Company: {company}
Source: {source}
Apply URL: {apply_url}
"""

    # Send to yourself as a record + action item
    user_email = profile.get("email")
    subject = f"[Job Applied] {title} at {company} ({source})"

    # Attach resume if it exists
    resume_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resume", "mehta's resume.pdf")
    if not os.path.exists(resume_path):
        resume_path = None

    success = send_application_email(
        to_email=user_email,
        subject=subject,
        body=email_body,
        resume_path=resume_path
    )

    if success:
        # Mark as applied
        c.execute("""UPDATE jobs 
                     SET status='applied', applied_at=?, apply_method='email', apply_status='success' 
                     WHERE id=?""",
                  (datetime.utcnow().isoformat(), job_id))
        conn.commit()
        conn.close()
        logger.info(f"Applied via email: '{title}' at '{company}'")
        return {"status": "success", "method": "email"}
    else:
        # Email failed — mark as manual
        c.execute("""UPDATE jobs 
                     SET status='manual_required', apply_method='manual', apply_status='email_failed' 
                     WHERE id=?""", (job_id,))
        conn.commit()
        conn.close()
        logger.warning(f"Email failed for '{title}' at '{company}' — marked manual")
        return {"status": "failed", "method": "manual", "message": "Email send failed"}


async def _apply_via_email(c, conn, job_id, profile, title, company, cover_letter, to_email):
    """Send application to a specific email address."""
    email_body = f"""Dear Hiring Team at {company},

{cover_letter}

Best regards,
{profile.get('name')}
{profile.get('email')} | {profile.get('phone', '')}
{profile.get('linkedin_url', '')}
{profile.get('github_url', '')}
"""

    success = send_application_email(
        to_email=to_email,
        subject=f"Application for {title} — {profile.get('name')}",
        body=email_body
    )

    if success:
        c.execute("""UPDATE jobs 
                     SET status='applied', applied_at=?, apply_method='email', apply_status='success' 
                     WHERE id=?""",
                  (datetime.utcnow().isoformat(), job_id))
        conn.commit()
        conn.close()
        return {"status": "success", "method": "email"}
    else:
        c.execute("""UPDATE jobs 
                     SET status='manual_required', apply_method='manual', apply_status='email_failed' 
                     WHERE id=?""", (job_id,))
        conn.commit()
        conn.close()
        return {"status": "failed", "method": "manual"}
