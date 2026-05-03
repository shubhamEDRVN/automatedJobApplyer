import os
import logging
import httpx
import urllib.parse
from typing import List, Dict, Any
from datetime import datetime
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    # ── Wellfound (AngelList) API ──────────────────────────────────

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

                search_term = urllib.parse.quote(keywords)
                url = f"https://wellfound.com/role/r/software-engineer/india"
                logger.info(f"Scraping Wellfound: {url}")

                await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

                try:
                    await page.wait_for_selector("[class*='styles_jobListingCard'], [class*='JobCard']", timeout=10000)
                except:
                    logger.warning("Wellfound: No job cards found or page structure changed.")
                    await browser.close()
                    return jobs

                cards = await page.query_selector_all("[class*='styles_jobListingCard'], [class*='JobCard']")
                for card in cards[:15]:
                    title_elem = await card.query_selector("a[class*='jobTitle'], h2 a, a[data-test='job-name']")
                    company_elem = await card.query_selector("a[class*='companyName'], h2 + a, span[class*='company']")
                    loc_elem = await card.query_selector("span[class*='location'], [class*='Location']")

                    title = (await title_elem.inner_text()).strip() if title_elem else ""
                    company = (await company_elem.inner_text()).strip() if company_elem else ""
                    location = (await loc_elem.inner_text()).strip() if loc_elem else "India"

                    href = await title_elem.get_attribute("href") if title_elem else ""
                    apply_url = f"https://wellfound.com{href}" if href and not href.startswith("http") else (href or url)

                    if not title:
                        continue

                    jobs.append({
                        "title": title,
                        "company": company or "Startup (Wellfound)",
                        "location": location,
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

    # ── Main Runner ────────────────────────────────────────────────

    async def run_all(self, keywords: str, location: str) -> List[Dict[str, Any]]:
        """Run all scrapers in parallel and combine results."""
        import asyncio

        results = await asyncio.gather(
            self.fetch_internshala_jobs(keywords),
            self.fetch_naukri_jobs(keywords, location),
            self.fetch_adzuna_jobs(keywords, location),
            self.fetch_wellfound_jobs(keywords),
            self.fetch_remoteok_jobs(keywords),
            return_exceptions=True
        )

        all_jobs = []
        for res in results:
            if isinstance(res, list):
                all_jobs.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Scraper task resulted in an exception: {res}")

        logger.info(f"Total jobs fetched across all platforms: {len(all_jobs)}")
        return all_jobs
