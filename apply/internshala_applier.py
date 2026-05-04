### File: apply/internshala_applier.py
"""
Internshala Quick Apply automation — logs into Internshala and submits
applications using Playwright browser automation.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__) # NEW


class InternshalaApplier: # NEW
    """Handles authenticated Internshala Quick Apply submissions.""" # NEW

    def __init__(self) -> None: # NEW
        """Initialize with Internshala credentials from environment.""" # NEW
        self.email: str = os.environ.get("INTERNSHALA_EMAIL", "") # NEW
        self.password: str = os.environ.get("INTERNSHALA_PASSWORD", "") # NEW
        self.session_cookies: Optional[List[Dict[str, Any]]] = None # NEW

    async def login(self, browser: Browser) -> bool: # NEW
        """Login to Internshala and cache session cookies. Returns True on success.""" # NEW
        if not self.email or not self.password: # NEW
            logger.error("INTERNSHALA_EMAIL or INTERNSHALA_PASSWORD not set in .env") # NEW
            return False # NEW

        page: Optional[Page] = None # NEW
        try: # NEW
            context = await browser.new_context( # NEW
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" # NEW
            ) # NEW
            page = await context.new_page() # NEW
            await page.goto("https://internshala.com/login/student", timeout=20000) # NEW
            await page.wait_for_timeout(2000) # NEW

            # Fill login form
            await page.fill('#email', self.email) # NEW
            await page.fill('#password', self.password) # NEW
            await page.click('#login_submit') # NEW

            # Wait for redirect away from /login
            try: # NEW
                await page.wait_for_url(lambda url: "/login" not in url, timeout=10000) # NEW
                self.session_cookies = await context.cookies() # NEW
                logger.info("Internshala: Login successful") # NEW
                await page.close() # NEW
                await context.close() # NEW
                return True # NEW
            except Exception: # NEW
                error_elem = await page.query_selector('.error-message, .alert-danger, .error_message') # NEW
                error_text = (await error_elem.inner_text()).strip() if error_elem else "Unknown error" # NEW
                logger.error(f"Internshala: Login failed — {error_text}") # NEW
                await page.close() # NEW
                await context.close() # NEW
                return False # NEW
        except Exception as e: # NEW
            logger.error(f"Internshala: Login exception — {e}") # NEW
            if page: # NEW
                try: # NEW
                    await page.close() # NEW
                except: # NEW
                    pass # NEW
            return False # NEW

    async def apply_to_job(self, apply_url: str, profile: Dict[str, Any], cover_letter: str) -> Dict[str, Any]: # NEW
        """Navigate to Internshala job page and submit Quick Apply. Returns result dict.""" # NEW
        if "internshala.com" not in apply_url: # NEW
            return {"status": "wrong_platform", "message": "Not an Internshala URL"} # NEW

        browser = None # NEW
        try: # NEW
            async with async_playwright() as p: # NEW
                browser = await p.chromium.launch(headless=True) # NEW

                # Step 1 — Restore or create session
                if not self.session_cookies: # NEW
                    success = await self.login(browser) # NEW
                    if not success: # NEW
                        await browser.close() # NEW
                        return {"status": "login_failed", "message": "Could not login to Internshala"} # NEW

                context: BrowserContext = await browser.new_context( # NEW
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" # NEW
                ) # NEW
                await context.add_cookies(self.session_cookies) # NEW
                page: Page = await context.new_page() # NEW

                # Step 2 — Navigate to job detail page
                logger.info(f"Internshala: Navigating to {apply_url}") # NEW
                await page.goto(apply_url, timeout=20000, wait_until="domcontentloaded") # NEW
                await page.wait_for_timeout(2000) # NEW

                # Step 3 — Find and click "Apply Now" button
                apply_btn_selectors = [ # NEW
                    "#apply_now_btn", # NEW
                    ".apply-now-btn", # NEW
                    "button:has-text('Apply now')", # NEW
                    "a:has-text('Apply now')", # NEW
                    "#easy_apply_btn", # NEW
                    "button:has-text('Apply Now')", # NEW
                    ".apply_now_btn", # NEW
                    "#continue_button" # NEW
                ] # NEW
                apply_btn = None # NEW
                for sel in apply_btn_selectors: # NEW
                    apply_btn = await page.query_selector(sel) # NEW
                    if apply_btn: # NEW
                        break # NEW

                if apply_btn is None: # NEW
                    logger.warning(f"Internshala: No apply button found on {apply_url}") # NEW
                    await page.close() # NEW
                    await browser.close() # NEW
                    return {"status": "no_apply_button", "message": "Could not find apply button on page"} # NEW

                await apply_btn.click() # NEW
                await page.wait_for_timeout(2000) # NEW

                # Step 4 — Handle the application modal/form

                # Cover letter textarea
                cl_selectors = ['#cover_letter', 'textarea[name="cover_letter"]', 'textarea[placeholder*="cover"]', 'textarea[placeholder*="Cover"]'] # NEW
                for cl_sel in cl_selectors: # NEW
                    cl_elem = await page.query_selector(cl_sel) # NEW
                    if cl_elem: # NEW
                        await cl_elem.fill("") # NEW — clear existing content
                        trimmed_letter = cover_letter[:2000] # NEW — Internshala 2000 char limit
                        await cl_elem.type(trimmed_letter, delay=30) # NEW — char-by-char to avoid bot detection
                        logger.info("Internshala: Filled cover letter field") # NEW
                        break # NEW

                # Availability question
                avail_selectors = ['select[name="availability"]', 'select[name*="available"]', '#availability'] # NEW
                for av_sel in avail_selectors: # NEW
                    av_elem = await page.query_selector(av_sel) # NEW
                    if av_elem: # NEW
                        try: # NEW
                            await av_elem.select_option(label="Immediately") # NEW
                            logger.info("Internshala: Set availability to 'Immediately'") # NEW
                        except: # NEW
                            try: # NEW
                                await av_elem.select_option(index=1) # NEW — fallback: first non-default option
                            except: # NEW
                                pass # NEW
                        break # NEW

                # Text input for availability (some forms use text instead of dropdown)
                avail_input_selectors = ['input[name*="available"]', 'input[placeholder*="available"]'] # NEW
                for avi_sel in avail_input_selectors: # NEW
                    avi_elem = await page.query_selector(avi_sel) # NEW
                    if avi_elem: # NEW
                        await avi_elem.fill("Yes, I can join immediately") # NEW
                        break # NEW

                # "Why should you be hired" textarea
                why_selectors = ['textarea[name*="why"]', 'textarea[placeholder*="hired"]', 'textarea[placeholder*="Hired"]', '#assessment_answer'] # NEW
                for why_sel in why_selectors: # NEW
                    why_elem = await page.query_selector(why_sel) # NEW
                    if why_elem: # NEW
                        why_text = cover_letter[:500] # NEW — shorter version for this field
                        await why_elem.fill("") # NEW
                        await why_elem.type(why_text, delay=30) # NEW
                        logger.info("Internshala: Filled 'why should you be hired' field") # NEW
                        break # NEW

                # Step 5 — Submit
                submit_selectors = [ # NEW
                    "#submit", # NEW
                    "button[type='submit']", # NEW
                    "button:has-text('Submit application')", # NEW
                    "button:has-text('Submit')", # NEW
                    "#submit_application", # NEW
                    ".submit-btn", # NEW
                    "input[type='submit']" # NEW
                ] # NEW

                submitted = False # NEW
                for sub_sel in submit_selectors: # NEW
                    sub_btn = await page.query_selector(sub_sel) # NEW
                    if sub_btn: # NEW
                        await sub_btn.click() # NEW
                        await page.wait_for_timeout(3000) # NEW

                        # Check for success indicators
                        success_selectors = [ # NEW
                            ".success-message", # NEW
                            ".application-submitted", # NEW
                            ".congrats", # NEW
                            "text=successfully applied", # NEW
                            "text=Application submitted", # NEW
                            "text=Congratulations" # NEW
                        ] # NEW
                        for ss in success_selectors: # NEW
                            success_elem = await page.query_selector(ss) # NEW
                            if success_elem: # NEW
                                submitted = True # NEW
                                break # NEW

                        # Also check page content for success keywords
                        if not submitted: # NEW
                            content = await page.content() # NEW
                            content_lower = content.lower() # NEW
                            if any(kw in content_lower for kw in ["successfully applied", "application submitted", "congratulations"]): # NEW
                                submitted = True # NEW

                        if submitted: # NEW
                            break # NEW

                if submitted: # NEW
                    logger.info(f"Internshala: Successfully applied to {apply_url}") # NEW
                    await page.close() # NEW
                    await browser.close() # NEW
                    return {"status": "success", "method": "internshala_quick_apply"} # NEW
                else: # NEW
                    # Take screenshot for debugging
                    try: # NEW
                        os.makedirs("logs", exist_ok=True) # NEW
                        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S") # NEW
                        screenshot_path = f"logs/internshala_fail_{timestamp}.png" # NEW
                        await page.screenshot(path=screenshot_path) # NEW
                        logger.warning(f"Internshala: Submit did not confirm success. Screenshot: {screenshot_path}") # NEW
                    except Exception as ss_err: # NEW
                        logger.warning(f"Internshala: Could not take debug screenshot — {ss_err}") # NEW

                    await page.close() # NEW
                    await browser.close() # NEW
                    return {"status": "failed", "method": "internshala_quick_apply", "message": "Submit did not confirm success"} # NEW

        except Exception as e: # NEW
            logger.error(f"Internshala apply failed for {apply_url}: {e}") # NEW
            if browser: # NEW
                try: # NEW
                    await browser.close() # NEW
                except: # NEW
                    pass # NEW
            return {"status": "error", "method": "internshala_quick_apply", "message": str(e)[:300]} # NEW
