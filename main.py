from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database import init_db

# Initialize local SQLite database
init_db()

app = FastAPI(
    title="Automated Internship Platform",
    description="Backend for automated internship & job application platform",
    version="1.0.0"
)

# Include routers
from routers.profile import router as profile_router
from routers.cover_letter import router as cover_letter_router
from routers.jobs import router as jobs_router

app.include_router(profile_router)
app.include_router(cover_letter_router)
app.include_router(jobs_router)

@app.get("/health", summary="Health Check")
async def health_check():
    """
    Health check endpoint to ensure the API is running correctly.
    """
    logger.info("Health check endpoint hit.")
    return JSONResponse(content={"status": "ok"})

if __name__ == "__main__":
    import uvicorn
    # Run the application using uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
