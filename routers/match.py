from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ai.matcher import match_jobs

router = APIRouter(prefix="/match", tags=["match"])

@router.post("/{profile_id}", response_model=List[Dict[str, Any]])
async def trigger_matching(profile_id: str):
    """
    Triggers the AI matching process for a given profile against all new jobs.
    Returns a list of matched jobs sorted by score.
    """
    try:
        matched_jobs = await match_jobs(profile_id)
        return matched_jobs
    except ValueError as e:
        # Catch errors like missing profile or API key
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch unexpected errors
        raise HTTPException(status_code=500, detail=f"An error occurred during matching: {str(e)}")
