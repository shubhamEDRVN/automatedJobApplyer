### File: scrapers/job_scraper.py
import os
import asyncio
import logging
import httpx
import urllib.parse
from typing import List, Dict, Any
from datetime import datetime
from playwright.async_api import async_playwright
from collections import Counter # NEW

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JobSpyScraper — LinkedIn, Glassdoor, Indeed via python-jobspy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class JobSpyScraper: # NEW
    """Scrapes LinkedIn, Glassdoor, Indeed using python-jobspy library.""" # NEW

    async def scrape(self, keywords: str, location: str, max_results: int = 25) -> List[Dict[str, Any]]: # NEW
        """Scrape LinkedIn, Glassdoor, Indeed via jobspy library. Returns list of job dicts.""" # NEW
        try: # NEW
            # Step 1 — Lazy import to avoid crash if jobspy not installed
            try: # NEW
                from jobspy import scrape_jobs # NEW
            except ImportError: # NEW
                logger.error("jobspy not installed. Run: pip install python-jobspy") # NEW
                return [] # NEW

            # Step 2 — Call scrape_jobs in thread pool (it's synchronous)
            loop = asyncio.get_event_loop() # NEW
            search_location = location if location.lower() != "remote" else "India" # NEW
            df = await loop.run_in_executor(None, lambda: scrape_jobs( # NEW
                site_name=["linkedin", "glassdoor", "indeed"], # NEW
                search_term=keywords, # NEW
                location=search_location, # NEW
                results_wanted=max_results, # NEW
                hours_old=48, # NEW
                country_indeed="India", # NEW
                linkedin_fetch_description=True # NEW
            )) # NEW

            # Step 3 — Handle None or empty DataFrame
            if df is None or len(df) == 0: # NEW
                logger.info(f"jobspy: No results for '{keywords}' in '{location}'") # NEW
                return [] # NEW

            # Step 4 — Convert each DataFrame row to a job dict
            jobs = [] # NEW
            source_counts: Counter = Counter() # NEW
            for row in df.itertuples(): # NEW
                title = str(getattr(row, "title", "") or "") # NEW
                company = str(getattr(row, "company", "") or "") # NEW
                location_str = str(getattr(row, "location", "") or "") # NEW
                description = str(getattr(row, "description", "") or "") # NEW
                apply_url = str(getattr(row, "job_url", "") or "") # NEW
                source = str(getattr(row, "site", "jobspy")).lower() # NEW
                posted = str(getattr(row, "date_posted", "") or "") or datetime.utcnow().isoformat() # NEW
                source_job_id = str(getattr(row, "id", "") or "") # NEW

                # Skip garbage listings
                if not title or not apply_url: # NEW
                    continue # NEW
                if len(description) < 100: # NEW
                    continue # NEW

                source_counts[source] += 1 # NEW
                jobs.append({ # NEW
                    "title": title, # NEW
                    "company": company or "Unknown Company", # NEW
                    "location": location_str or "India", # NEW
                    "description": description[:3000], # NEW
                    "apply_url": apply_url, # NEW
                    "source": source, # NEW
                    "source_job_id": source_job_id, # NEW
                    "posted_date": posted, # NEW
                    "fetched_at": datetime.utcnow().isoformat() # NEW
                }) # NEW

            # Step 5 — Log count per source
            total = len(jobs) # NEW
            linkedin_n = source_counts.get("linkedin", 0) # NEW
            glassdoor_n = source_counts.get("glassdoor", 0) # NEW
            indeed_n = source_counts.get("indeed", 0) # NEW
            logger.info(f"jobspy: {total} jobs — LinkedIn: {linkedin_n}, Glassdoor: {glassdoor_n}, Indeed: {indeed_n}") # NEW
            return jobs # NEW

        except Exception as e: # NEW
            logger.error(f"jobspy scrape failed for '{keywords}': {e}", exc_info=True) # NEW
            return [] # NEW


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JobScraper — Internshala, Naukri, Adzuna, Wellfound, RemoteOK + jobspy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class JobScraper:
    def __init__(self):
        self.adzuna_app_id = os.environ.get("ADZUNA_APP_ID", "")
        self.adzuna_app_key = os.environ.get("ADZUNA_APP_KEY", "")
        self.timeout = 20000  # 20s timeout for slower Indian sites

    # ── Internshala ────────────────────────────────────────────────

    async def fetch_internshala_jobs(self, keywords: str) -> List[Dict[str, Any]]:
        """Scrape internships from Internshala using Playwright."""
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                search_term = keywords.replace(" ", "-")
                url = f"https://internshala.com/internships/keywords-{search_term}/"
                logger.info(f"Scraping Internshala: {url}")

                await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

                # Try multiple possible selectors for job cards
                card_selector = None
                for sel in [".individual_internship", ".internship_meta", ".container-fluid.individual_internship"]:
                    try:
                        await page.wait_for_selector(sel, timeout=8000)
                        card_selector = sel
                        break
                    except:
                        continue

                if not card_selector:
                    logger.warning("Internshala: No job cards found.")
                    await browser.close()
                    return jobs

                cards = await page.query_selector_all(card_selector)
                for card in cards[:15]:
                    # Try multiple selectors for title
                    title = ""
                    for ts in [".heading_4_5 a", ".job-internship-name a", "h3 a", ".profile a", ".heading_4_5"]:
                        elem = await card.query_selector(ts)
                        if elem:
                            title = (await elem.inner_text()).strip()
                            if title:
                                break

                    # Company name
                    company = ""
                    for cs in [".company_name a", ".company_name", ".comp-name", "h4 a"]:
                        elem = await card.query_selector(cs)
                        if elem:
                            company = (await elem.inner_text()).strip()
                            if company:
                                break

                    # Location
                    location = ""
                    for ls in ["#location_names a", "#location_names", ".locations a", ".location_link"]:
                        elem = await card.query_selector(ls)
                        if elem:
                            location = (await elem.inner_text()).strip()
                            if location:
                                break

                    # Apply URL
                    apply_url = ""
                    link_elem = await card.query_selector("a[href*='/internship/detail/']")
                    if not link_elem:
                        link_elem = await card.query_selector(".heading_4_5 a")
                    if not link_elem:
                        link_elem = await card.query_selector("a")
                    if link_elem:
                        href = await link_elem.get_attribute("href")
                        if href:
                            apply_url = f"https://internshala.com{href}" if not href.startswith("http") else href

                    # Stipend
                    stipend = ""
                    for ss in [".stipend", ".desktop-i span"]:
                        elem = await card.query_selector(ss)
                        if elem:
                            stipend = (await elem.inner_text()).strip()
                            break

                    if not title and not company:
                        continue

                    jobs.append({
                        "title": title or "Internship",
                        "company": company or "Unknown Company",
                        "location": location or "India",
                        "description": f"Internship at {company}. Stipend: {stipend}. Apply on Internshala.",
                        "apply_url": apply_url,
                        "source": "internshala",
                        "posted_date": datetime.utcnow().isoformat()
                    })

                await browser.close()
                logger.info(f"Internshala: Fetched {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Internshala scraper failed: {e}")

        return jobs

    # ── Naukri ─────────────────────────────────────────────────────

    async def fetch_naukri_jobs(self, keywords: str, location: str) -> List[Dict[str, Any]]:
        """Scrape jobs from Naukri (India's #1 job portal) using Playwright."""
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                search_kw = keywords.replace(" ", "-")
                search_loc = location.replace(" ", "-") if location else ""
                url = f"https://www.naukri.com/{search_kw}-jobs-in-{search_loc}"
                logger.info(f"Scraping Naukri: {url}")

                await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

                try:
                    await page.wait_for_selector(".srp-jobtuple-wrapper, .jobTuple", timeout=10000)
                except:
                    logger.warning("Naukri: No job cards found or blocked by captcha.")
                    await browser.close()
                    return jobs

                cards = await page.query_selector_all(".srp-jobtuple-wrapper, .jobTuple")
                for card in cards[:15]:
                    title_elem = await card.query_selector(".title, a.title")
                    company_elem = await card.query_selector(".comp-dtls-wrap a, .comp-name")
                    loc_elem = await card.query_selector(".locWdth, .loc-wrap .loc")
                    desc_elem = await card.query_selector(".job-desc, .job-desc-container")

                    title = (await title_elem.inner_text()).strip() if title_elem else ""
                    company = (await company_elem.inner_text()).strip() if company_elem else ""
                    location_text = (await loc_elem.inner_text()).strip() if loc_elem else ""
                    description = (await desc_elem.inner_text()).strip() if desc_elem else "Job from Naukri"

                    apply_url = await title_elem.get_attribute("href") if title_elem else url

                    if not title:
                        continue

                    jobs.append({
                        "title": title,
                        "company": company or "Unknown Company",
                        "location": location_text or "India",
                        "description": description,
                        "apply_url": apply_url or url,
                        "source": "naukri",
                        "posted_date": datetime.utcnow().isoformat()
                    })

                await browser.close()
                logger.info(f"Naukri: Fetched {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Naukri scraper failed: {e}")

        return jobs

    # ── Adzuna API ─────────────────────────────────────────────────

    async def fetch_adzuna_jobs(self, keywords: str, location: str) -> List[Dict[str, Any]]:
        """Fetch jobs from Adzuna API (India endpoint)."""
        jobs = []
        if not self.adzuna_app_id or not self.adzuna_app_key:
            logger.info("Adzuna credentials not found. Skipping Adzuna scraper.")
            return jobs

        url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
        params = {
            "app_id": self.adzuna_app_id,
            "app_key": self.adzuna_app_key,
            "results_per_page": 25,
            "what": keywords,
            "where": location if location.lower() != "remote" else "India",
            "content-type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                for item in data.get("results", []):
                    jobs.append({
                        "title": item.get("title", ""),
                        "company": item.get("company", {}).get("display_name", "Unknown Company"),
                        "location": item.get("location", {}).get("display_name", "India"),
                        "description": item.get("description", "Job from Adzuna"),
                        "apply_url": item.get("redirect_url", ""),
                        "source": "adzuna",
                        "posted_date": item.get("created", datetime.utcnow().isoformat())
                    })
            logger.info(f"Adzuna (India): Fetched {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Adzuna scraper failed: {e}")

        return jobs

    # ── Wellfound (AngelList) ──────────────────────────────────────

    async def fetch_wellfound_jobs(self, keywords: str) -> List[Dict[str, Any]]:
        """Scrape startup jobs from Wellfound (formerly AngelList Talent)."""
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                encoded_kw = urllib.parse.quote(keywords)
                url = f"https://wellfound.com/jobs?q={encoded_kw}&l=india"
                logger.info(f"Scraping Wellfound: {url}")

                await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

                # Wait for any known job card selector with 15s timeout
                card_found = False
                card_wait_selectors = [
                    "[data-test='StartupResult']",
                    "[class*='JobListing']",
                    "[class*='job-listing']",
                    "h2 a[href*='/jobs/']",
                    "[class*='styles_jobListingCard']",
                    "[class*='JobCard']"
                ]
                for sel in card_wait_selectors:
                    try:
                        await page.wait_for_selector(sel, timeout=15000)
                        card_found = True
                        break
                    except:
                        continue

                if not card_found:
                    logger.warning(f"Wellfound: No results found for '{keywords}' — possible selector change or bot detection")
                    await browser.close()
                    return jobs

                # Scroll down to load more results (JS-rendered page)
                await page.evaluate("window.scrollBy(0, 2000)")
                await asyncio.sleep(1.5)
                await page.evaluate("window.scrollBy(0, 2000)")
                await asyncio.sleep(1.5)

                # Gather all possible card elements
                card_selectors = [
                    "[data-test='StartupResult']",
                    "[class*='styles_jobListingCard']",
                    "[class*='JobCard']",
                    "[class*='JobListing']",
                    "[class*='job-listing']"
                ]
                cards = []
                for cs in card_selectors:
                    cards = await page.query_selector_all(cs)
                    if cards:
                        break

                # Multi-selector extraction patterns
                title_selectors = ["a[class*='jobTitle']", "h2 a", "[data-test='role'] a", "[class*='JobTitle'] a"]
                company_selectors = ["[class*='companyName']", "[data-test='company-name']", "h2 + div a", "[class*='StartupName']"]
                location_selectors = ["[class*='location']", "[data-test='location']", "span[class*='Location']"]

                for card in cards[:15]:
                    title = ""
                    title_href = ""
                    for ts in title_selectors:
                        elem = await card.query_selector(ts)
                        if elem:
                            title = (await elem.inner_text()).strip()
                            title_href = await elem.get_attribute("href") or ""
                            if title:
                                break

                    company = ""
                    for cs_sel in company_selectors:
                        elem = await card.query_selector(cs_sel)
                        if elem:
                            company = (await elem.inner_text()).strip()
                            if company:
                                break

                    location = ""
                    for ls in location_selectors:
                        elem = await card.query_selector(ls)
                        if elem:
                            location = (await elem.inner_text()).strip()
                            if location:
                                break

                    apply_url = f"https://wellfound.com{title_href}" if title_href and not title_href.startswith("http") else (title_href or url)

                    if not title:
                        continue

                    jobs.append({
                        "title": title,
                        "company": company or "Startup (Wellfound)",
                        "location": location or "India",
                        "description": f"Startup job at {company}. Found on Wellfound.",
                        "apply_url": apply_url,
                        "source": "wellfound",
                        "posted_date": datetime.utcnow().isoformat()
                    })

                await browser.close()
                logger.info(f"Wellfound: Fetched {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Wellfound scraper failed: {e}")

        return jobs

    # ── RemoteOK (Remote-first jobs) ───────────────────────────────

    async def fetch_remoteok_jobs(self, keywords: str) -> List[Dict[str, Any]]:
        """Fetch remote jobs from RemoteOK.com API (JSON endpoint, no auth)."""
        jobs = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://remoteok.com/api",
                    headers={"User-Agent": "AutomatedInternshipPlatform/1.0"}
                )
                response.raise_for_status()
                data = response.json()

                kw_lower = keywords.lower().split()
                for item in data[1:]:  # First item is metadata
                    title = item.get("position", "")
                    desc = item.get("description", "")
                    tags = " ".join(item.get("tags", []))
                    combined = f"{title} {desc} {tags}".lower()

                    # Filter to matching keywords
                    if any(kw in combined for kw in kw_lower):
                        jobs.append({
                            "title": title,
                            "company": item.get("company", "Unknown Company"),
                            "location": "Remote",
                            "description": desc[:2000] or "Remote job from RemoteOK",
                            "apply_url": item.get("url", f"https://remoteok.com/remote-jobs/{item.get('slug', '')}"),
                            "source": "remoteok",
                            "posted_date": item.get("date", datetime.utcnow().isoformat())
                        })

                    if len(jobs) >= 15:
                        break

            logger.info(f"RemoteOK: Fetched {len(jobs)} matching jobs")
        except Exception as e:
            logger.error(f"RemoteOK scraper failed: {e}")

        return jobs

    # ── Unstop (internships) ───────────────────────────────────────── # NEW

    async def fetch_unstop_jobs(self, keywords: str) -> List[Dict[str, Any]]: # NEW
        """Scrape internships from Unstop.com using Playwright.""" # NEW
        jobs: List[Dict[str, Any]] = [] # NEW
        browser = None # NEW
        try: # NEW
            async with async_playwright() as p: # NEW
                browser = await p.chromium.launch(headless=True) # NEW
                context = await browser.new_context( # NEW
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", # NEW
                    viewport={"width": 1280, "height": 800} # NEW
                ) # NEW
                page = await context.new_page() # NEW
                page.set_default_timeout(25000) # NEW
                await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"}) # NEW

                encoded = urllib.parse.quote(keywords) # NEW
                url = f"https://unstop.com/internships?search={encoded}&oppType=internship" # NEW
                logger.info(f"Scraping Unstop internships: {url}") # NEW

                await page.goto(url, timeout=25000, wait_until="domcontentloaded") # NEW
                await page.wait_for_timeout(3000) # NEW — Unstop is heavily JS-rendered

                # Card detection — try multiple selectors
                card_selector = None # NEW
                for sel in [".opportunity-card", ".card-body", "[class*='oppor']", "[class*='card_dtls']"]: # NEW
                    try: # NEW
                        await page.wait_for_selector(sel, timeout=15000) # NEW
                        card_selector = sel # NEW
                        break # NEW
                    except: # NEW
                        continue # NEW

                if not card_selector: # NEW
                    logger.warning(f"Unstop: No cards found for '{keywords}' — site may have changed selectors") # NEW
                    await browser.close() # NEW
                    return jobs # NEW

                cards = await page.query_selector_all(card_selector) # NEW
                title_sels = [".oppor-title a", "h2 a", ".title a", "[class*='title'] a", "h3"] # NEW
                company_sels = [".org-name", ".company-name", "[class*='org']", "[class*='company']"] # NEW
                location_sels = [".location", "[class*='location']", "[class*='place']"] # NEW
                stipend_sels = [".stipend", "[class*='stipend']", "[class*='salary']"] # NEW
                duration_sels = [".duration", "[class*='duration']"] # NEW

                for card in cards[:20]: # NEW
                    try: # NEW
                        # Title
                        title = "" # NEW
                        title_href = "" # NEW
                        for ts in title_sels: # NEW
                            elem = await card.query_selector(ts) # NEW
                            if elem: # NEW
                                title = (await elem.inner_text()).strip() # NEW
                                title_href = await elem.get_attribute("href") or "" # NEW
                                if title: # NEW
                                    break # NEW

                        if not title: # NEW
                            continue # NEW

                        # Company
                        company = "" # NEW
                        for cs in company_sels: # NEW
                            elem = await card.query_selector(cs) # NEW
                            if elem: # NEW
                                company = (await elem.inner_text()).strip() # NEW
                                if company: # NEW
                                    break # NEW

                        # Location
                        location = "" # NEW
                        for ls in location_sels: # NEW
                            elem = await card.query_selector(ls) # NEW
                            if elem: # NEW
                                location = (await elem.inner_text()).strip() # NEW
                                if location: # NEW
                                    break # NEW

                        # Stipend
                        stipend = "" # NEW
                        for ss in stipend_sels: # NEW
                            elem = await card.query_selector(ss) # NEW
                            if elem: # NEW
                                stipend = (await elem.inner_text()).strip() # NEW
                                if stipend: # NEW
                                    break # NEW

                        # Duration
                        duration = "" # NEW
                        for ds in duration_sels: # NEW
                            elem = await card.query_selector(ds) # NEW
                            if elem: # NEW
                                duration = (await elem.inner_text()).strip() # NEW
                                if duration: # NEW
                                    break # NEW

                        apply_url = f"https://unstop.com{title_href}" if title_href and not title_href.startswith("http") else (title_href or url) # NEW

                        jobs.append({ # NEW
                            "title": title, # NEW
                            "company": company or "Unknown (Unstop)", # NEW
                            "location": location or "Remote/India", # NEW
                            "description": f"Internship at {company}. Stipend: {stipend or 'Not specified'}. Duration: {duration or 'Not specified'}. Apply on Unstop.", # NEW
                            "apply_url": apply_url, # NEW
                            "source": "unstop", # NEW
                            "job_type": "internship", # NEW
                            "posted_date": datetime.utcnow().isoformat() # NEW
                        }) # NEW
                    except Exception as card_err: # NEW
                        logger.warning(f"Unstop: Failed to parse one card — {card_err}") # NEW
                        continue # NEW

                await browser.close() # NEW
                logger.info(f"Unstop: Fetched {len(jobs)} internships for '{keywords}'") # NEW
        except Exception as e: # NEW
            logger.error(f"Unstop internship scraper failed: {e}") # NEW
            if browser: # NEW
                try: # NEW
                    await browser.close() # NEW
                except: # NEW
                    pass # NEW

        return jobs # NEW

    # ── Unstop (competitions / hackathons) ──────────────────────────── # NEW

    async def fetch_unstop_competitions(self, keywords: str) -> List[Dict[str, Any]]: # NEW
        """Scrape hackathons & competitions from Unstop.com using Playwright.""" # NEW
        jobs: List[Dict[str, Any]] = [] # NEW
        browser = None # NEW
        try: # NEW
            async with async_playwright() as p: # NEW
                browser = await p.chromium.launch(headless=True) # NEW
                context = await browser.new_context( # NEW
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", # NEW
                    viewport={"width": 1280, "height": 800} # NEW
                ) # NEW
                page = await context.new_page() # NEW
                page.set_default_timeout(25000) # NEW
                await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"}) # NEW

                encoded = urllib.parse.quote(keywords) # NEW
                url = f"https://unstop.com/competitions?search={encoded}" # NEW
                logger.info(f"Scraping Unstop competitions: {url}") # NEW

                await page.goto(url, timeout=25000, wait_until="domcontentloaded") # NEW
                await page.wait_for_timeout(3000) # NEW

                # Card detection
                card_selector = None # NEW
                for sel in [".opportunity-card", ".card-body", "[class*='oppor']", "[class*='card_dtls']"]: # NEW
                    try: # NEW
                        await page.wait_for_selector(sel, timeout=15000) # NEW
                        card_selector = sel # NEW
                        break # NEW
                    except: # NEW
                        continue # NEW

                if not card_selector: # NEW
                    logger.warning(f"Unstop competitions: No cards found for '{keywords}'") # NEW
                    await browser.close() # NEW
                    return jobs # NEW

                cards = await page.query_selector_all(card_selector) # NEW
                title_sels = [".oppor-title a", "h2 a", ".title a", "[class*='title'] a", "h3"] # NEW
                company_sels = [".org-name", ".company-name", "[class*='org']", "[class*='company']"] # NEW

                for card in cards[:20]: # NEW
                    try: # NEW
                        title = "" # NEW
                        title_href = "" # NEW
                        for ts in title_sels: # NEW
                            elem = await card.query_selector(ts) # NEW
                            if elem: # NEW
                                title = (await elem.inner_text()).strip() # NEW
                                title_href = await elem.get_attribute("href") or "" # NEW
                                if title: # NEW
                                    break # NEW

                        if not title: # NEW
                            continue # NEW

                        company = "" # NEW
                        for cs in company_sels: # NEW
                            elem = await card.query_selector(cs) # NEW
                            if elem: # NEW
                                company = (await elem.inner_text()).strip() # NEW
                                if company: # NEW
                                    break # NEW

                        apply_url = f"https://unstop.com{title_href}" if title_href and not title_href.startswith("http") else (title_href or url) # NEW

                        jobs.append({ # NEW
                            "title": title, # NEW
                            "company": company or "Unknown (Unstop)", # NEW
                            "location": "Online", # NEW
                            "description": f"Competition/Hackathon by {company}. Register on Unstop.", # NEW
                            "apply_url": apply_url, # NEW
                            "source": "unstop_competition", # NEW
                            "job_type": "competition", # NEW
                            "posted_date": datetime.utcnow().isoformat() # NEW
                        }) # NEW
                    except Exception as card_err: # NEW
                        logger.warning(f"Unstop competition: Failed to parse one card — {card_err}") # NEW
                        continue # NEW

                await browser.close() # NEW
                logger.info(f"Unstop: Fetched {len(jobs)} competitions for '{keywords}'") # NEW
        except Exception as e: # NEW
            logger.error(f"Unstop competition scraper failed: {e}") # NEW
            if browser: # NEW
                try: # NEW
                    await browser.close() # NEW
                except: # NEW
                    pass # NEW

        return jobs # NEW

    # ── Y Combinator / Work at a Startup ───────────────────────────── # NEW

    async def fetch_yc_jobs(self, keywords: str) -> List[Dict[str, Any]]: # NEW
        """Scrape engineering jobs/internships from Y Combinator's Work at a Startup platform.""" # NEW
        jobs: List[Dict[str, Any]] = [] # NEW
        browser = None # NEW
        try: # NEW
            async with async_playwright() as p: # NEW
                browser = await p.chromium.launch(headless=True) # NEW
                context = await browser.new_context( # NEW
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", # NEW
                    viewport={"width": 1280, "height": 800} # NEW
                ) # NEW
                page = await context.new_page() # NEW

                # Primary URL with keyword search
                encoded = urllib.parse.quote(keywords) # NEW
                primary_url = f"https://www.workatastartup.com/jobs?q={encoded}&remote=true&role=eng&jobType=intern" # NEW
                fallback_url = "https://www.workatastartup.com/jobs?remote=true&role=eng&jobType=intern" # NEW

                logger.info(f"Scraping YC Work at a Startup: {primary_url}") # NEW
                await page.goto(primary_url, timeout=25000, wait_until="networkidle") # NEW
                await page.wait_for_timeout(4000) # NEW — generous wait for React hydration

                # Card detection
                card_selector = None # NEW
                for sel in ["[data-test='job-card']", ".jobs-grid a", "[class*='JobCard']", "li[class*='job']", "[class*='job-listing']", "a[href*='/jobs/']"]: # NEW
                    try: # NEW
                        await page.wait_for_selector(sel, timeout=15000) # NEW
                        card_selector = sel # NEW
                        break # NEW
                    except: # NEW
                        continue # NEW

                # Fallback URL if primary found nothing
                if not card_selector: # NEW
                    logger.info(f"YC primary URL returned no results, trying fallback: {fallback_url}") # NEW
                    await page.goto(fallback_url, timeout=25000, wait_until="networkidle") # NEW
                    await page.wait_for_timeout(4000) # NEW
                    for sel in ["[data-test='job-card']", ".jobs-grid a", "[class*='JobCard']", "li[class*='job']", "[class*='job-listing']", "a[href*='/jobs/']"]: # NEW
                        try: # NEW
                            await page.wait_for_selector(sel, timeout=15000) # NEW
                            card_selector = sel # NEW
                            break # NEW
                        except: # NEW
                            continue # NEW

                if not card_selector: # NEW
                    logger.warning(f"YC Work at a Startup: No job cards found for '{keywords}' — site structure may have changed") # NEW
                    await browser.close() # NEW
                    return jobs # NEW

                cards = await page.query_selector_all(card_selector) # NEW
                company_sels = ["[data-test='company-name']", "h2", "h3", "[class*='company']", "[class*='Company']"] # NEW
                role_sels = ["[data-test='role']", "h3", "h4", "[class*='role']", "[class*='title']"] # NEW
                location_sels = ["[data-test='location']", "[class*='location']", "[class*='Location']", "span:has-text('Remote')"] # NEW
                desc_sels = ["[data-test='company-description']", "p", "[class*='description']"] # NEW

                for card in cards[:25]: # NEW
                    try: # NEW
                        # Company name
                        company_name = "" # NEW
                        for cs in company_sels: # NEW
                            elem = await card.query_selector(cs) # NEW
                            if elem: # NEW
                                company_name = (await elem.inner_text()).strip() # NEW
                                if company_name: # NEW
                                    break # NEW

                        # Job title
                        job_title = "" # NEW
                        for rs in role_sels: # NEW
                            elem = await card.query_selector(rs) # NEW
                            if elem: # NEW
                                text = (await elem.inner_text()).strip() # NEW
                                if text and text != company_name: # NEW — avoid duplication
                                    job_title = text # NEW
                                    break # NEW

                        if not job_title: # NEW
                            continue # NEW

                        # Location
                        location = "" # NEW
                        for ls in location_sels: # NEW
                            elem = await card.query_selector(ls) # NEW
                            if elem: # NEW
                                location = (await elem.inner_text()).strip() # NEW
                                if location: # NEW
                                    break # NEW

                        # Company description snippet
                        company_desc = "" # NEW
                        for ds in desc_sels: # NEW
                            elem = await card.query_selector(ds) # NEW
                            if elem: # NEW
                                company_desc = (await elem.inner_text()).strip()[:200] # NEW
                                if company_desc: # NEW
                                    break # NEW

                        # Apply URL from card's <a> tag
                        href = "" # NEW
                        if card.as_element(): # NEW
                            href = await card.get_attribute("href") or "" # NEW
                        if not href: # NEW
                            link = await card.query_selector("a") # NEW
                            if link: # NEW
                                href = await link.get_attribute("href") or "" # NEW
                        apply_url = f"https://www.workatastartup.com{href}" if href and not href.startswith("http") else (href or primary_url) # NEW

                        # Determine job type
                        job_type = "internship" if "intern" in job_title.lower() else "full_time" # NEW

                        description = f"{job_title} at {company_name} (YC-backed startup). {company_desc}. Apply on Work at a Startup." # NEW

                        jobs.append({ # NEW
                            "title": job_title, # NEW
                            "company": company_name or "YC Startup", # NEW
                            "location": location or "Remote", # NEW
                            "description": description, # NEW
                            "apply_url": apply_url, # NEW
                            "source": "yc_startup", # NEW
                            "job_type": job_type, # NEW
                            "posted_date": datetime.utcnow().isoformat() # NEW
                        }) # NEW
                    except Exception as card_err: # NEW
                        logger.warning(f"YC: Failed to parse one card — {card_err}") # NEW
                        continue # NEW

                await browser.close() # NEW
                logger.info(f"YC Work at a Startup: Fetched {len(jobs)} jobs for '{keywords}'") # NEW
        except Exception as e: # NEW
            logger.error(f"YC Work at a Startup scraper failed: {e}") # NEW
            if browser: # NEW
                try: # NEW
                    await browser.close() # NEW
                except: # NEW
                    pass # NEW

        return jobs # NEW

    async def fetch_yc_companies_hiring(self) -> Dict[str, Any]: # NEW
        """Fetches recently-funded YC companies that are currently hiring.""" # NEW
        result: Dict[str, Any] = {"companies": [], "count": 0} # NEW
        browser = None # NEW
        try: # NEW
            async with async_playwright() as p: # NEW
                browser = await p.chromium.launch(headless=True) # NEW
                context = await browser.new_context( # NEW
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", # NEW
                    viewport={"width": 1280, "height": 800} # NEW
                ) # NEW
                page = await context.new_page() # NEW

                url = "https://www.ycombinator.com/companies?isHiring=true&batch=W25&batch=S24" # NEW
                logger.info(f"Fetching YC companies hiring: {url}") # NEW
                await page.goto(url, timeout=25000, wait_until="networkidle") # NEW
                await page.wait_for_timeout(3000) # NEW

                # Try to find company cards
                card_selector = None # NEW
                for sel in ["a[class*='Company']", "[class*='_company_']", "a[href*='/companies/']"]: # NEW
                    try: # NEW
                        await page.wait_for_selector(sel, timeout=10000) # NEW
                        card_selector = sel # NEW
                        break # NEW
                    except: # NEW
                        continue # NEW

                if not card_selector: # NEW
                    logger.warning("YC companies: No company cards found") # NEW
                    await browser.close() # NEW
                    return result # NEW

                cards = await page.query_selector_all(card_selector) # NEW
                companies = [] # NEW
                for card in cards[:50]: # NEW
                    try: # NEW
                        name_elem = await card.query_selector("span, h3, h4, [class*='name']") # NEW
                        name = (await name_elem.inner_text()).strip() if name_elem else "" # NEW
                        href = await card.get_attribute("href") or "" # NEW
                        company_url = f"https://www.ycombinator.com{href}" if href and not href.startswith("http") else href # NEW
                        if name: # NEW
                            companies.append({"name": name, "url": company_url}) # NEW
                    except: # NEW
                        continue # NEW

                result = {"companies": companies, "count": len(companies)} # NEW
                await browser.close() # NEW

                # Log at INFO so it appears in daily run logs
                company_names = [c["name"] for c in companies[:10]] # NEW
                logger.info(f"YC companies hiring (W25/S24): {result['count']} total. Top 10: {', '.join(company_names)}") # NEW
        except Exception as e: # NEW
            logger.error(f"YC companies scraper failed: {e}") # NEW
            if browser: # NEW
                try: # NEW
                    await browser.close() # NEW
                except: # NEW
                    pass # NEW

        return result # NEW

    # ── JobSpy wrapper (LinkedIn + Glassdoor + Indeed) ────────────

    async def fetch_jobspy_jobs(self, keywords: str, location: str) -> List[Dict[str, Any]]:
        """Fetch jobs from LinkedIn, Glassdoor, Indeed via python-jobspy."""
        scraper = JobSpyScraper()
        return await scraper.scrape(keywords, location, max_results=25)

    # ── Main Runner ────────────────────────────────────────────────

    async def run_all(self, keywords: str, location: str) -> List[Dict[str, Any]]:
        """Run all scrapers in parallel and combine results."""
        results = await asyncio.gather(
            self.fetch_internshala_jobs(keywords),
            self.fetch_naukri_jobs(keywords, location),
            self.fetch_adzuna_jobs(keywords, location),
            self.fetch_wellfound_jobs(keywords),
            self.fetch_remoteok_jobs(keywords),
            self.fetch_jobspy_jobs(keywords, location),
            self.fetch_unstop_jobs(keywords),
            self.fetch_unstop_competitions(keywords),
            self.fetch_yc_jobs(keywords), # NEW
            return_exceptions=True
        )

        all_jobs = []
        for res in results:
            if isinstance(res, list):
                all_jobs.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Scraper task resulted in an exception: {res}")

        # Fire-and-forget: log YC companies hiring (non-blocking info for the daily digest)
        try: # NEW
            yc_info = await self.fetch_yc_companies_hiring() # NEW
            logger.info(f"YC hiring companies logged: {yc_info['count']} companies") # NEW
        except Exception as e: # NEW
            logger.warning(f"YC company listing failed (non-critical): {e}") # NEW

        logger.info(f"Total jobs fetched across all platforms: {len(all_jobs)}")
        return all_jobs

