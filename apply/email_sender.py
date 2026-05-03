import os
import httpx
import logging
import base64
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_application_email(to_email: str, subject: str, body: str, resume_path: Optional[str] = None) -> bool:
    """
    Sends an application email via Brevo (Sendinblue) HTTP API.
    Bypasses SMTP completely, avoiding regional ISP port bans.
    Requires BREVO_API_KEY and SENDER_EMAIL in environment.
    """
    api_key = os.environ.get("BREVO_API_KEY")
    sender_email = os.environ.get("SENDER_EMAIL")
    
    if not api_key or not sender_email:
        logger.error("BREVO_API_KEY or SENDER_EMAIL missing. Cannot send email.")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    payload = {
        "sender": {"email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body
    }
    
    if resume_path and os.path.exists(resume_path):
        import mimetypes
        ctype, _ = mimetypes.guess_type(resume_path)
        if ctype is None:
            ctype = 'application/pdf'
            
        with open(resume_path, 'rb') as f:
            resume_data = f.read()
            
        encoded_resume = base64.b64encode(resume_data).decode('utf-8')
        payload["attachment"] = [
            {
                "content": encoded_resume,
                "name": os.path.basename(resume_path)
            }
        ]

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
        logger.info(f"Successfully sent application email to {to_email} via HTTP API")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via HTTP API: {e}")
        return False
