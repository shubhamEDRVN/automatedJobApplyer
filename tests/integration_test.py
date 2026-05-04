### File: tests/integration_test.py
import sys
import os
import asyncio
import logging
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_db, get_db
from ai.llm_router import get_llm_router
from scrapers.job_scraper import JobScraper
from ai.matcher import match_jobs
from ai.cover_letter import generate_cover_letter
from apply.form_filler import auto_apply
from apply.email_sender import send_application_email

logging.basicConfig(level=logging.ERROR) # keep it quiet for tests
logger = logging.getLogger(__name__)

async def run_tests() -> None:
    """Run all end-to-end integration tests for the AutoApply pipeline."""
    print("\nStarting AutoApply Integration Tests...\n")
    results = []

    # Get a profile_id
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, email FROM profiles LIMIT 1")
        row = c.fetchone()
        if not row:
            print("ERROR: No profile found in database. Please run dashboard and create one.")
            sys.exit(1)
        profile_id, profile_email = row[0], row[1]

    # TEST 1 — Database health
    print("Testing 1. Database health...")
    try:
        init_db()
        expected_tables = ["profiles", "skills", "projects", "preferences", "jobs", "cover_letters", "resume_tailoring"]
        missing = []
        with get_db() as conn:
            c = conn.cursor()
            for t in expected_tables:
                c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'")
                if not c.fetchone():
                    missing.append(t)
        if missing:
            results.append(("1. Database health", f"FAIL - Missing: {', '.join(missing)}"))
        else:
            results.append(("1. Database health", "PASS"))
    except Exception as e:
        results.append(("1. Database health", f"FAIL - {e}"))

    # TEST 2 — LLM Router health
    print("Testing 2. LLM Router (Gemini/key1)...")
    try:
        router = get_llm_router()
        resp = await router.generate("You are a test assistant.", "Reply with the single word: OK", json_mode=False)
        if "OK" in resp or "ok" in resp.lower():
            results.append(("2. LLM Router", "PASS"))
        else:
            print(f"LLM Router FAIL: Unexpected response -> {resp}")
            results.append(("2. LLM Router", f"FAIL - Unexpected response: {resp}"))
    except Exception as e:
        print(f"LLM Router FAIL: Exception -> {e}")
        results.append(("2. LLM Router", f"FAIL - Exception: {e}"))

    # TEST 3 — Scraper health
    print("Testing 3. Scraper health (RemoteOK)...")
    try:
        scraper = JobScraper()
        jobs = await scraper.fetch_remoteok_jobs("python developer")
        if isinstance(jobs, list):
            results.append(("3. Scraper health", "PASS"))
        else:
            results.append(("3. Scraper health", "FAIL - Did not return a list"))
    except Exception as e:
        results.append(("3. Scraper health", f"FAIL - {e}"))

    # TEST 4 — Matcher smoke test
    print("Testing 4. Matcher smoke test...")
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM jobs WHERE id='test-job-001'")
            c.execute('''INSERT INTO jobs (id, title, company, description, apply_url, source, profile_id, status)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      ('test-job-001', 'Full Stack Developer Intern', 'Test Corp', 'We need React, Node.js, MongoDB...', 'https://example.com', 'test', profile_id, 'new'))
            conn.commit()

        await match_jobs(profile_id)

        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT match_score FROM jobs WHERE id='test-job-001'")
            row = c.fetchone()
            if row and row[0] is not None and row[0] > 0:
                results.append(("4. Matcher smoke test", "PASS"))
            else:
                results.append(("4. Matcher smoke test", "FAIL - Score not set or zero"))
            c.execute("DELETE FROM jobs WHERE id='test-job-001'")
            conn.commit()
    except Exception as e:
        results.append(("4. Matcher smoke test", f"FAIL - {e}"))

    # TEST 5 — Cover letter smoke test
    print("Testing 5. Cover letter smoke test...")
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM jobs WHERE id='test-job-002'")
            c.execute("DELETE FROM cover_letters WHERE job_id='test-job-002'")
            c.execute('''INSERT INTO jobs (id, title, company, description, apply_url, source, profile_id, status, match_score, matched_skills)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      ('test-job-002', 'Full Stack Developer Intern', 'Test Corp', 'We need React, Node.js, MongoDB...', 'https://example.com', 'test', profile_id, 'matched', 85, '["React","Node.js"]'))
            conn.commit()

        letter = await generate_cover_letter('test-job-002', profile_id)
        word_count = len(letter.split())
        if 50 <= word_count <= 500:
            results.append(("5. Cover letter smoke test", "PASS"))
        else:
            results.append(("5. Cover letter smoke test", f"FAIL - Word count out of bounds ({word_count})"))

        with get_db() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM jobs WHERE id='test-job-002'")
            c.execute("DELETE FROM cover_letters WHERE job_id='test-job-002'")
            conn.commit()
    except Exception as e:
        results.append(("5. Cover letter smoke test", f"FAIL - {e}"))

    # TEST 6 — Apply engine smoke test
    print("Testing 6. Apply engine smoke test...")
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM jobs WHERE id='test-job-003'")
            c.execute('''INSERT INTO jobs (id, title, company, description, apply_url, source, profile_id, status)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      ('test-job-003', 'Full Stack Developer Intern', 'Test Corp', 'We need React...', 'mailto:test@example.com', 'test', profile_id, 'matched'))
            conn.commit()

        with patch('apply.form_filler.send_application_email') as mock_send:
            mock_send.return_value = True
            res = await auto_apply('test-job-003', profile_id)
            if res.get("status") in ["success", "manual_required"]:
                results.append(("6. Apply engine smoke test", "PASS"))
            else:
                results.append(("6. Apply engine smoke test", f"FAIL - Unexpected status: {res.get('status')}"))

        with get_db() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM jobs WHERE id='test-job-003'")
            conn.commit()
    except Exception as e:
        results.append(("6. Apply engine smoke test", f"FAIL - {e}"))

    # TEST 7 — Email sender health
    print("Testing 7. Email sender health...")
    try:
        success = send_application_email(profile_email, "AutoApply Integration Test", "This is an automated test. Platform is working correctly.", None)
        if success:
            results.append(("7. Email sender health", "PASS"))
        else:
            results.append(("7. Email sender health", "FAIL - Returned False"))
    except Exception as e:
        results.append(("7. Email sender health", f"FAIL - {e}"))

    # Print Summary
    print("\n+---------------------------------+--------+")
    print("| Test                            | Result |")
    print("+---------------------------------+--------+")
    for t_name, t_res in results:
        t_res_clean = "PASS" if t_res.startswith("PASS") else "FAIL"
        print(f"| {t_name:<31} | {t_res_clean:<6} |")
    print("+---------------------------------+--------+")

    passed_count = sum(1 for r in results if r[1].startswith("PASS"))
    print(f"Overall: {passed_count}/{len(results)} tests passed\n")

    if passed_count < len(results):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_tests())
