# 🚀 AutoApply — Autonomous Job Application Pipeline

AutoApply is a production-grade, end-to-end automated internship and job application platform. It autonomously scrapes job listings across 9+ platforms, uses an intelligent multi-provider LLM router to evaluate fit, tailors resumes to bypass ATS systems, generates highly personalized cover letters, and auto-submits applications.

## ✨ Key Features

- **Multi-Source Job Scraping**: Synchronously and asynchronously scrapes jobs from Internshala, Naukri, Wellfound, RemoteOK, YC Work at a Startup, and Unstop. Also integrates `python-jobspy` for LinkedIn, Glassdoor, and Indeed.
- **AI-Driven Matcher & Router**: Utilizes a highly resilient LLM Router supporting multiple API keys across Gemini, Groq, and OpenRouter (free tiers) with automatic rate-limit fallbacks to calculate custom match scores based on your specific profile.
- **ATS Resume Tailoring**: Automatically parses job descriptions and generates customized project bullets and keyword strings to bypass ATS parsers.
- **Dynamic Cover Letters**: Selects the most relevant projects from your portfolio to craft highly personalized, context-aware cover letters.
- **Autonomous Application Engine**: Uses headless Playwright to navigate complex platforms (like Internshala) to fill out forms and bypass Captchas, while using Brevo to send direct email applications.
- **Engagement Engine**: A smart scheduler that automatically follows up on applied jobs after 7 days and sends you a comprehensive Daily Digest.
- **Premium Dashboard**: A pure HTML/CSS/JS frontend dashboard to monitor application history, view match scores, manage manual applications, and manually trigger the pipeline.

## 🛠️ Tech Stack

- **Backend**: Python 3.11, FastAPI
- **Database**: SQLite
- **Scraping & Automation**: Playwright (Async), `python-jobspy`
- **AI & NLP**: Google Gemini API, Groq API, OpenRouter API
- **Email Delivery**: Brevo (Sendinblue)
- **Frontend**: Vanilla HTML/CSS/JS (Zero external dependencies)

## 📂 Project Structure

```text
automatedJobApplyer/
├── ai/                     # AI components (LLM Router, Cover Letters, ATS Tailoring, Matcher)
├── apply/                  # Application mechanisms (Playwright Form Filler, Brevo Email Sender)
├── frontend/               # Single-page dashboard application (index.html)
├── routers/                # FastAPI endpoint routers
├── scheduler/              # Automated daily tasks, follow-ups, and email digests
├── scrapers/               # Multi-platform async job scrapers
├── tests/                  # Integration tests for CI/CD validation
├── database.py             # SQLite database initialization and management
└── main.py                 # FastAPI application entry point
```

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- Playwright browsers installed (`playwright install chromium`)
- API Keys for Gemini, Groq, Brevo, and Adzuna (all available on free tiers)

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/yourusername/AutoApply.git
cd AutoApply
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Variables
Create a `.env` file in the root directory (refer to `.env.example`):
```env
# AI Providers
GEMINI_API_KEY=your_gemini_key
GEMINI_API_KEY_2=your_gemini_backup_key
GROQ_API_KEY=your_groq_key

# Scraper Credentials
INTERNSHALA_EMAIL=your_email
INTERNSHALA_PASSWORD=your_password
ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key

# Email Provider
BREVO_API_KEY=your_brevo_key
SENDER_EMAIL=your_email@gmail.com
```

### 4. Run the Platform
Start the FastAPI server:
```bash
uvicorn main:app --reload
```
Open `http://localhost:8000` (or the respective frontend path) to access the dashboard. Create your profile via the Settings tab to begin.

### 5. Trigger the Pipeline
You can trigger the pipeline manually via the dashboard, or run the background script:
```bash
python scheduler/daily_run.py
```

## ✅ Testing & Deployment
Before deploying or relying on the autonomous agent, run the integration test suite to verify database health, LLM connectivity, scraper health, and email readiness:
```bash
python tests/integration_test.py
```
Please refer to `PRODUCTION_CHECKLIST.md` for a complete list of pre-flight checks before your first live run.

## 📄 License
This project is for personal use to automate internship/job applications. Please use responsibly to avoid spamming platforms or violating terms of service.
