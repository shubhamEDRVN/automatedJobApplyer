### File: PRODUCTION_CHECKLIST.md

# AutoApply Production Readiness Checklist

Complete this checklist before running the first real autonomous application pipeline.

## Section 1 — Environment
1. [ ] All `.env` variables set and loaded correctly.
2. [ ] `GEMINI_API_KEY` (and backups) verified and active.
3. [ ] `BREVO_API_KEY` verified, and sender email validated in Brevo dashboard.
4. [ ] `INTERNSHALA_EMAIL` and `INTERNSHALA_PASSWORD` are correct and login works.
5. [ ] Adzuna API keys (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`) obtained and active.

## Section 2 — Profile setup
6. [ ] Profile created via the frontend dashboard.
7. [ ] Full resume text pasted accurately, matching the latest PDF version.
8. [ ] Skills list is accurate and complete (minimum 10 skills).
9. [ ] Projects added with real GitHub URLs and high-impact descriptions.
10. [ ] Target roles set (minimum 5 role keywords like "Software Engineer", "Backend Intern").
11. [ ] Target locations set (e.g., "Remote", "Bangalore").
12. [ ] `min_match_score` set to 68 in Settings.
13. [ ] `max_apply_per_day` set to 15 in Settings.

## Section 3 — Dry run verification
14. [ ] Ran `python scheduler/daily_run.py --dry-run` without errors.
15. [ ] Digest email successfully received with correct job counts.
16. [ ] At least 20 jobs found and 5+ matched during the dry run.
17. [ ] No "Apply engine" errors observed in `logs/daily_run_*.log`.
18. [ ] Sample cover letters reviewed in dashboard; quality is ATS-optimized and acceptable.

## Section 4 — Platform safety
19. [ ] GitHub Actions secrets all added (`GEMINI_API_KEY`, `BREVO_API_KEY`, `INTERNSHALA_EMAIL`, `INTERNSHALA_PASSWORD`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`).
20. [ ] `.gitignore` verified (`.env`, `logs/`, `uploads/`, `*.sqlite3` all listed).
21. [ ] `MAX_APPLICATIONS_PER_RUN` set conservatively (≤ 15 for the first week).
22. [ ] Internshala account NOT flagged (manually check account health by logging in).
23. [ ] Brevo daily limit confirmed (300 free emails/day limit understood).

## Section 5 — First live run
24. [ ] Run manually the first time (NOT via GitHub Actions — watch logs live).
25. [ ] Confirm applied jobs appear in dashboard with correct status (`applied`).
26. [ ] Check email inbox for daily digest and application carbon copies.
27. [ ] Verify no duplicate applications were sent to the same company.
28. [ ] Set GitHub Actions to `enabled` for daily automation.
