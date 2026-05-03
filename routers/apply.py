from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from apply.form_filler import auto_apply

router = APIRouter(prefix="/apply", tags=["apply"])

@router.post("/{job_id}/{profile_id}", response_model=Dict[str, Any])
async def trigger_auto_apply(job_id: str, profile_id: str):
    """
    Triggers the auto-apply process for a specific job and profile.
    Attempts to fill a form or send an email application automatically.
    """
    try:
        result = await auto_apply(job_id, profile_id)
        
        # If the status is an error or manual_required, we might still return 200 OK
        # with the status details, but let's return 400 for hard errors.
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
            
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error during application: {str(e)}")
