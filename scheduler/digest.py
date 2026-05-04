import os
import logging
from typing import List, Dict, Any
from apply.email_sender import send_application_email

logger = logging.getLogger(__name__)

def send_daily_digest(profile: Dict[str, Any], stats: Dict[str, int], applied_jobs: List[Dict[str, Any]], followups_sent: List[Dict[str, Any]] = None) -> bool: # CHANGED
    """
    Builds and sends a daily summary email to the user with: 
    number of new jobs found, number matched, number applied, 
    list of companies applied to with job titles.
    """
    to_email = profile.get("email")
    if not to_email:
        logger.error(f"Profile {profile.get('id')} has no email. Cannot send digest.")
        return False
        
    subject = "Your Daily Automated Job Hunt Summary"
    
    body = f"Hello {profile.get('name', 'Applicant')},\n\n"
    body += "Here is the summary of your automated job hunt today:\n\n"
    
    body += f"📊 Stats:\n"
    body += f"- New Jobs Found: {stats.get('new_found', 0)}\n"
    body += f"- Jobs Matched: {stats.get('matched', 0)}\n"
    body += f"- Applications Submitted: {stats.get('applied', 0)}\n\n"
    
    if applied_jobs:
        body += "✅ Applications Submitted Today:\n"
        for job in applied_jobs:
            company = job.get('company', 'Unknown Company')
            title = job.get('title', 'Unknown Title')
            method = job.get('apply_method', 'unknown method')
            body += f"- {title} at {company} (via {method})\n"
    else:
        body += "No applications were submitted today.\n"
        
    if followups_sent: # NEW
        body += "\n🔁 FOLLOW-UPS SENT TODAY:\n" # NEW
        for f in followups_sent: # NEW
            f_company = f.get('company', 'Unknown Company') # NEW
            f_title = f.get('title', 'Unknown Title') # NEW
            body += f"- {f_title} at {f_company}\n" # NEW

        
    body += "\nGood luck!\nAutomated Internship Platform"

    return send_application_email(
        to_email=to_email,
        subject=subject,
        body=body
    )
