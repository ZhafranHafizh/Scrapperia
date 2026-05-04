"""
Google Search Scraper via Selenium Chrome (headless)

Menggunakan Chrome headless untuk scraping Google Search.
Lebih reliable dibanding HTTP-only scraper karena:
  - Bypass consent page
  - Render JavaScript
  - Mendapatkan hasil lengkap (title, snippet, URL)
"""

import time
import random
from typing import Optional
from dataclasses import dataclass, field

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


@dataclass
class GoogleResult:
    """Single Google search result."""
    title: str = ""
    description: str = ""
    url: str = ""
    date: Optional[object] = None
    source: str = ""


class GoogleScraper:
    """Google Search scraper using Selenium Chrome headless."""

    GOOGLE_URL = "https://www.google.com/search"

    # Time range → Google tbs parameter
    TBS_MAP = {
        "d": "qdr:d",   # last day
        "w": "qdr:w",   # last week
        "m": "qdr:m",   # last month
        "y": "qdr:y",   # last year
    }

    def __init__(self):
        self._driver: Optional[webdriver.Chrome] = None

    def _get_driver(self) -> webdriver.Chrome:
        """Create or reuse a Chrome headless driver."""
        if self._driver is not None:
            try:
                # Test if driver is still alive
                _ = self._driver.title
                return self._driver
            except Exception:
                self._close_driver()

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        # Suppress logging
        options.add_argument("--log-level=3")
        options.add_experimental_option(
            "prefs", {"profile.default_content_setting_values.notifications": 2}
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Spoof navigator.webdriver
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )

        self._driver = driver
        return driver

    def _close_driver(self):
        """Safely close the Chrome driver."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def _handle_consent(self, driver: webdriver.Chrome):
        """Handle Google consent page if it appears."""
        try:
            # Check for consent buttons (various languages)
            consent_selectors = [
                "button#L2AGLb",           # English: "I agree"
                "button[aria-label*='Accept']",
                "button[aria-label*='Terima']",
                "form[action*='consent'] button",
                "button[aria-label*='Setuju']",
            ]
            for selector in consent_selectors:
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(1)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def search(
        self,
        query: str,
        lang: str = "id",
        num_results: int = 10,
        time_range: str = "",
        mode: str = "text",
    ) -> list[GoogleResult]:
        """
        Search Google and return results.

        Args:
            query: Search query string
            lang: Language code (id, en, es, etc.)
            num_results: Number of results to fetch
            time_range: Time filter (d=day, w=week, m=month, y=year, ""=all)
            mode: Search mode (text, news)

        Returns:
            List of GoogleResult objects
        """
        driver = self._get_driver()

        # Build URL params
        params = {
            "q": query,
            "num": str(min(num_results + 2, 50)),  # Request a few extra
            "hl": lang,
            "gl": lang,  # Geo-location hint
        }

        # Time range filter
        tbs = self.TBS_MAP.get(time_range, "")
        if tbs:
            params["tbs"] = tbs

        # News mode
        if mode == "news":
            params["tbm"] = "nws"

        # Build URL
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.GOOGLE_URL}?{param_str}"

        try:
            driver.get(url)
            time.sleep(random.uniform(1.5, 3.0))

            # Handle consent page
            self._handle_consent(driver)

            # Wait for search results to load
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#search, #rso, .g"))
                )
            except Exception:
                # Try scrolling to trigger lazy load
                driver.execute_script("window.scrollTo(0, 300)")
                time.sleep(1)

            results: list[GoogleResult] = []

            if mode == "news":
                results = self._parse_news_results(driver, num_results)
            else:
                results = self._parse_text_results(driver, num_results)

            return results

        except Exception as e:
            print(f"   ⚠️ Google search error: {e}")
            return []

    def _parse_text_results(self, driver: webdriver.Chrome, max_results: int) -> list[GoogleResult]:
        """Parse text search results from the page."""
        results: list[GoogleResult] = []

        # Primary selector: standard Google search results
        selectors = [
            "div.g",                    # Standard results
            "div[data-sokoban-container]",  # Alternative container
            "div.tF2Cxc",              # Inner result container
        ]

        result_elements = []
        for sel in selectors:
            result_elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if result_elements:
                break

        for elem in result_elements[:max_results]:
            try:
                result = GoogleResult()

                # Title
                try:
                    h3 = elem.find_element(By.CSS_SELECTOR, "h3")
                    result.title = h3.text.strip()
                except Exception:
                    continue  # Skip results without title

                # URL
                try:
                    link = elem.find_element(By.CSS_SELECTOR, "a[href]")
                    href = link.get_attribute("href") or ""
                    if href and not href.startswith("javascript:"):
                        result.url = href
                except Exception:
                    pass

                # Description/snippet
                try:
                    # Try multiple snippet selectors
                    for desc_sel in [
                        "div[data-sncf] span",
                        "div.VwiC3b span",
                        "div.VwiC3b",
                        "span.aCOpRe",
                        "div[style='-webkit-line-clamp:2']",
                    ]:
                        try:
                            desc_elem = elem.find_element(By.CSS_SELECTOR, desc_sel)
                            if desc_elem.text.strip():
                                result.description = desc_elem.text.strip()
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # Source
                try:
                    cite = elem.find_element(By.CSS_SELECTOR, "cite")
                    result.source = cite.text.strip()
                except Exception:
                    pass

                if result.title and result.url:
                    results.append(result)

            except Exception:
                continue

        return results

    def _parse_news_results(self, driver: webdriver.Chrome, max_results: int) -> list[GoogleResult]:
        """Parse news search results from the page."""
        results: list[GoogleResult] = []

        # News results have different structure
        selectors = [
            "div.SoaBEf",       # News card container
            "div.dbsr",         # Alternative news container
            "article",          # Article element
            "div.g",            # Fallback to standard
        ]

        result_elements = []
        for sel in selectors:
            result_elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if result_elements:
                break

        for elem in result_elements[:max_results]:
            try:
                result = GoogleResult()

                # Title
                try:
                    for title_sel in ["div.mCBkyc", "div.JheGif", "h3", "a div[role='heading']"]:
                        try:
                            title_elem = elem.find_element(By.CSS_SELECTOR, title_sel)
                            if title_elem.text.strip():
                                result.title = title_elem.text.strip()
                                break
                        except Exception:
                            continue
                except Exception:
                    continue

                # URL
                try:
                    link = elem.find_element(By.CSS_SELECTOR, "a[href]")
                    href = link.get_attribute("href") or ""
                    if href and not href.startswith("javascript:"):
                        result.url = href
                except Exception:
                    pass

                # Description
                try:
                    for desc_sel in ["div.GI74Re", "div.Y3v8qd", "span"]:
                        try:
                            desc_elem = elem.find_element(By.CSS_SELECTOR, desc_sel)
                            if desc_elem.text.strip() and desc_elem.text.strip() != result.title:
                                result.description = desc_elem.text.strip()
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # Source
                try:
                    for src_sel in ["div.CEMjEf span", "g-img + span", "div.MgUUmf span"]:
                        try:
                            src_elem = elem.find_element(By.CSS_SELECTOR, src_sel)
                            if src_elem.text.strip():
                                result.source = src_elem.text.strip()
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                if result.title and result.url:
                    results.append(result)

            except Exception:
                continue

        return results

    def close(self):
        """Close the scraper and release resources."""
        self._close_driver()

    def __del__(self):
        self.close()


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

_scraper: Optional[GoogleScraper] = None


def google_search(
    query: str,
    lang: str = "id",
    num_results: int = 10,
    time_range: str = "",
    mode: str = "text",
) -> list[dict]:
    """
    Convenience function for Google search.

    Returns list of dicts with keys: title, description, link, date, source
    """
    global _scraper
    if _scraper is None:
        _scraper = GoogleScraper()

    results = _scraper.search(
        query=query,
        lang=lang,
        num_results=num_results,
        time_range=time_range,
        mode=mode,
    )

    return [
        {
            "title": r.title,
            "description": r.description,
            "link": r.url,
            "date": r.date,
            "source": r.source,
        }
        for r in results
    ]
