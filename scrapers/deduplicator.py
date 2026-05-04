### File: scrapers/deduplicator.py
import logging # NEW
from typing import List, Dict, Any

logger = logging.getLogger(__name__) # NEW

def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]: # CHANGED
    """
    Takes a list of jobs, removes exact duplicates within the same source,
    and returns the clean list keeping cross-source duplicates.
    """
    original_count = len(jobs) # NEW
    
    # Dictionary to keep the best job for a given (title, company, source)
    best_jobs = {} # NEW
    
    for job in jobs: # CHANGED
        title = job.get("title", "").strip().lower() # CHANGED
        company = job.get("company", "").strip().lower() # CHANGED
        source = job.get("source", "").strip().lower() # NEW
        
        # Combine title, company, and source for within-source uniqueness
        key = f"{title}|{company}|{source}" # NEW
        
        if key not in best_jobs: # NEW
            best_jobs[key] = job # NEW
        else: # NEW
            # If we already have this job from this source, keep the one with the longest description
            existing_desc_len = len(best_jobs[key].get("description") or "") # NEW
            new_desc_len = len(job.get("description") or "") # NEW
            if new_desc_len > existing_desc_len: # NEW
                best_jobs[key] = job # NEW
                
    clean_jobs = list(best_jobs.values()) # NEW
    final_count = len(clean_jobs) # NEW
    removed = original_count - final_count # NEW
    
    logger.info(f"Deduplicator: {original_count} → {final_count} jobs ({removed} within-source duplicates removed)") # NEW
            
    return clean_jobs # CHANGED
