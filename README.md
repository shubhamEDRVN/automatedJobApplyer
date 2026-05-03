# Automated Internship & Job Application Platform

## How to run locally

1. **Clone the repository and navigate to the project directory** (if you haven't already):
   ```bash
   cd automatedInternship
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up Playwright browsers**:
   ```bash
   playwright install
   ```

6. **Set up environment variables**:
   - Copy `.env.example` to `.env`
   - Fill in your API keys and configuration values:
     ```bash
     cp .env.example .env
     ```

7. **Run the backend development server**:
   ```bash
   uvicorn main:app --reload
   ```

8. **Test the health check endpoint**:
   - Open your browser or use curl to check `http://localhost:8000/health`
"# automatedJobApplyer" 
