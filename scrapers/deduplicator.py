import hashlib
from typing import List, Dict, Any

def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Takes a list of jobs, removes duplicates by (title + company) hash,
    and returns the clean list.
    """
    seen_hashes = set()
    clean_jobs = []
    
    for job in jobs:
        # Normalize to lower case for better matching
        title = job.get("title", "").strip().lower()
        company = job.get("company", "").strip().lower()
        
        # Create a combined hash
        hash_string = f"{title}|{company}".encode('utf-8')
        job_hash = hashlib.md5(hash_string).hexdigest()
        
        if job_hash not in seen_hashes:
            seen_hashes.add(job_hash)
            clean_jobs.append(job)
            
    return clean_jobs
