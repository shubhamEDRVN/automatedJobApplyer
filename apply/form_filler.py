### File: apply/form_filler.py
"""
Auto-Apply Engine — Multiple strategies:
  1. Email application via Brevo (most reliable)
  2. Direct form filling via Playwright (best-effort)
  3. Mark as 'manual_required' if neither works
"""

import os
import re # NEW
import logging
from typing import Dict, Any, Optional # CHANGED
from datetime import datetime
from playwright.async_api import async_playwright, Page # NEW
from apply.email_sender import send_application_email
from apply.internshala_applier import InternshalaApplier # NEW
from database import get_db

_internshala_applier = InternshalaApplier() # NEW — singleton to cache login session

logger = logging.getLogger(__name__)

async def detect_apply_method(page: Page) -> str: # NEW
    """Detects the method of application from a given page."""
    url = page.url
    ats_domains = ["greenhouse.io", "lever.co", "workday.com", "taleo.net", "ashbyhq.com"]
    if any(domain in url for domain in ats_domains):
        return "simple_form"
    
    if await page.query_selector('form input[name], form textarea'):
        return "simple_form"
        
    if await page.query_selector('a[href^="mailto:"]'):
        return "email"
        
    return "manual"

async def extract_email_from_page(page: Page) -> Optional[str]: # NEW
    """Extracts an email address from the page content or mailto links."""
    elements = await page.query_selector_all('a[href^="mailto:"]')
    for el in elements:
        href = await el.get_attribute("href")
        if href:
            email = href.replace("mailto:", "").split("?")[0]
            if "@" in email and "." in email:
                return email
                
    content = await page.content()
    match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', content)
    if match:
        return match.group(0)
        
    return None

async def fill_and_submit_form(page: Page, profile: Dict[str, Any], cover_letter: str) -> bool: # NEW
    """Fills out a simple application form and submits it."""
    name_selectors = ['input[name*="name"]', 'input[placeholder*="name" i]', 'input[id*="name" i]']
    email_selectors = ['input[type="email"]', 'input[name*="email"]']
    phone_selectors = ['input[type="tel"]', 'input[name*="phone"]']
    cover_selectors = ['textarea[name*="cover"]', 'textarea[name*="message"]', 'textarea[name*="letter"]', 'textarea']
    linkedin_selectors = ['input[name*="linkedin"]', 'input[placeholder*="linkedin" i]']
    github_selectors = ['input[name*="github"]', 'input[placeholder*="github" i]']
    
    async def fill_first_found(selectors, value):
        for sel in selectors:
            el = await page.query_selector(sel)
            if el:
                await el.fill(value)
                return True
        return False
        
    await fill_first_found(name_selectors, profile.get("name", ""))
    await fill_first_found(email_selectors, profile.get("email", ""))
    await fill_first_found(phone_selectors, profile.get("phone", ""))
    await fill_first_found(cover_selectors, cover_letter)
    await fill_first_found(linkedin_selectors, profile.get("linkedin_url", ""))
    await fill_first_found(github_selectors, profile.get("github_url", ""))
    
    submit_selectors = ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Apply")', 'button:has-text("Submit")']
    for sel in submit_selectors:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            try:
                await page.wait_for_navigation(timeout=3000)
                return True
            except:
                content = await page.content()
                if "success" in content.lower() or "thank you" in content.lower():
                    return True
                return False
    return False

async def auto_apply(job_id: str, profile_id: str) -> Dict[str, Any]:
    """
    Attempts to auto-apply for a job using multiple strategies:
      1. Direct email via Brevo if mailto link exists.
      2. Playwright form detection (ATS forms, extract emails).
      3. Fallback to 'manual_required'.
    Updates job status in SQLite on success.
    """
    conn = get_db()
    c = conn.cursor()

    try: # CHANGED
        # Fetch job
        c.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
        j_row = c.fetchone()
        if not j_row:
            return {"status": "error", "message": "Job not found"}
        job = dict(j_row)

        if job.get("applied_at") is not None: # CHANGED
            return {"status": "already_applied"} # CHANGED

        # Fetch profile
        c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,))
        p_row = c.fetchone()
        if not p_row:
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

        resume_path = profile.get("resume_path") # CHANGED
        if not resume_path or not os.path.exists(resume_path): # CHANGED
            resume_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resume", "resume.pdf") # CHANGED
            
        if not os.path.exists(resume_path): # CHANGED
            logger.warning("Resume file not found — applying without attachment") # CHANGED
            resume_path = None # CHANGED
        elif os.path.getsize(resume_path) > 5 * 1024 * 1024: # CHANGED
            logger.warning("Resume file larger than 5MB — applying without attachment") # CHANGED
            resume_path = None # CHANGED

        # Strategy 0: Internshala Quick Apply (highest ROI for Indian internships)
        if source == "internshala" and "internshala.com" in apply_url: # NEW
            logger.info(f"Trying Internshala Quick Apply for '{title}' at '{company}'") # NEW
            result = await _internshala_applier.apply_to_job(apply_url, profile, cover_letter) # NEW
            if result.get("status") == "success": # NEW
                c.execute("""UPDATE jobs  # NEW
                             SET status='applied', applied_at=?, apply_method='internshala_quick_apply', apply_status='success' 
                             WHERE id=?""", (datetime.utcnow().isoformat(), job_id)) # NEW
                conn.commit() # NEW
                return {"status": "success", "method": "internshala_quick_apply"} # NEW
            else: # NEW
                logger.info(f"Internshala Quick Apply failed ({result.get('status')}), falling through to email strategy") # NEW

        # Strategy 1: mailto link
        if apply_url.startswith("mailto:"):
            to_email = apply_url.replace("mailto:", "").split("?")[0]
            return await _apply_via_email(c, conn, job_id, profile, title, company, cover_letter, to_email, resume_path)

        # Strategy 2: Playwright form detection
        method = "manual"
        async with async_playwright() as p: # NEW
            browser = await p.chromium.launch(headless=True) # NEW
            try: # NEW
                page = await browser.new_page() # NEW
                await page.goto(apply_url, timeout=20000) # NEW
                
                method_type = await detect_apply_method(page) # NEW
                if method_type == "simple_form": # NEW
                    success = await fill_and_submit_form(page, profile, cover_letter) # NEW
                    if success: # NEW
                        method = "form" # NEW
                        c.execute("""UPDATE jobs 
                                     SET status='applied', applied_at=?, apply_method='form', apply_status='success' 
                                     WHERE id=?""", (datetime.utcnow().isoformat(), job_id)) # NEW
                        conn.commit() # NEW
                        return {"status": "success", "method": "form"} # NEW
                elif method_type == "email": # NEW
                    extracted_email = await extract_email_from_page(page) # NEW
                    if extracted_email: # NEW
                        return await _apply_via_email(c, conn, job_id, profile, title, company, cover_letter, extracted_email, resume_path) # NEW
                
                # If "manual" or form submission failed
                c.execute("""UPDATE jobs 
                             SET status='manual_required', apply_method='manual', apply_status='pending' 
                             WHERE id=?""", (job_id,)) # NEW
                conn.commit() # NEW
                return {"status": "manual_required"} # NEW
            finally: # NEW
                await browser.close() # NEW

    except Exception as e: # CHANGED
        logger.warning(f"Automation failed for '{job.get('title', 'Unknown')}': {e}") # CHANGED
        apply_error = str(e)[:300] # CHANGED
        c.execute("""UPDATE jobs 
                     SET status='manual_required', apply_method='manual', apply_status='failed' 
                     WHERE id=?""", (job_id,)) # CHANGED
        conn.commit() # CHANGED
        return {"status": "manual_required", "reason": "automation_failed"} # CHANGED
    finally: # CHANGED
        conn.close() # CHANGED

async def _apply_via_email(c, conn, job_id, profile, title, company, cover_letter, to_email, resume_path): # CHANGED
    """Send application to a specific email address."""
    email_body = f"""Dear Hiring Team at {company},

{cover_letter}

Best regards,
{profile.get('name')}
{profile.get('email')} | {profile.get('phone', '')}
{profile.get('linkedin_url', '')}
{profile.get('github_url', '')}
"""

    success = send_application_email( # CHANGED
        to_email=to_email,
        subject=f"Application for {title} — {profile.get('name')}",
        body=email_body,
        resume_path=resume_path, # CHANGED
        cc_self=True, # CHANGED
        profile_email=profile.get('email') # CHANGED
    )

    if success:
        c.execute("""UPDATE jobs 
                     SET status='applied', applied_at=?, apply_method='email', apply_status='success' 
                     WHERE id=?""",
                  (datetime.utcnow().isoformat(), job_id))
        conn.commit()
        return {"status": "success", "method": "email"}
    else:
        c.execute("""UPDATE jobs 
                     SET status='manual_required', apply_method='manual', apply_status='email_failed' 
                     WHERE id=?""", (job_id,))
        conn.commit()
        return {"status": "failed", "method": "manual"}
