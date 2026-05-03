@echo off
REM ═══════════════════════════════════════════════════════════════
REM   Automated Internship Platform — Daily Runner
REM   Scheduled via Windows Task Scheduler to run at 10:00 AM IST
REM ═══════════════════════════════════════════════════════════════

REM Set working directory to project root
cd /d "C:\Users\shubham\OneDrive\Documents\automatedInternship"

REM Log start time
echo [%date% %time%] Starting daily job hunt... >> logs\scheduler.log

REM Run the pipeline using the venv Python
venv\Scripts\python.exe scheduler\daily_run.py >> logs\scheduler.log 2>&1

REM Log completion
echo [%date% %time%] Pipeline finished. >> logs\scheduler.log
echo ──────────────────────────────────────── >> logs\scheduler.log
