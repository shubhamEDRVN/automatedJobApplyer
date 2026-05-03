MATCHER_SYSTEM_PROMPT = """You are a job fit scorer. Return ONLY valid JSON."""

MATCHER_USER_PROMPT = """Profile:
{profile_json}

Job:
{job_json}

Return ONLY valid JSON with this exact structure, no markdown formatting:
{{
  "score": <0-100 integer>,
  "reasons": ["<reason 1>", "<reason 2>"],
  "matched_skills": ["<skill 1>", "<skill 2>"],
  "red_flags": ["<red flag 1>"]
}}"""

CL_SYSTEM_PROMPT = """You are an expert career coach and professional copywriter."""

CL_USER_PROMPT = """Write a 200-250 word professional cover letter for the following job application.
The letter must:
- Address the specific company by name
- Mention 2-3 skills that match the job from the applicant's profile
- Reference one project from the user's profile
- Have a clear call to action at the end.

Job Details:
{job_json}

Applicant Profile:
{profile_json}

Output ONLY the cover letter text. No introductory or concluding remarks."""
