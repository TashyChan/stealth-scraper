"""
Stealth Web Scraper
===================
Anti-detection techniques used:
  - TLS fingerprint spoofing via curl-cffi (impersonates real browsers)
  - Realistic browser headers (Accept, Accept-Language, Sec-Fetch-*, etc.)
  - Random User-Agent rotation
  - Human-like request timing with jitter
  - Automatic retry with exponential backoff
  - robots.txt respect (optional, defaults to allow if unreachable)
  - Session reuse (keeps cookies like a real browser)
  - Referer chain simulation
"""

import time
import random
import json
import csv
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import Optional

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# ── User-Agent pool ──────────────────────────────────────────────────────────
try:
    _ua = UserAgent(browsers=["chrome", "edge"])
    def random_ua() -> str:
        return _ua.random
except Exception:
    _FALLBACK_UAS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    ]
    def random_ua() -> str:
        return random.choice(_FALLBACK_UAS)


# ── Stealth Session ──────────────────────────────────────────────────────────
class StealthSession:
    """
    A requests-like session that impersonates a real Chrome browser at the
    TLS/JA3 fingerprint level (via curl-cffi) and adds realistic HTTP headers.
    """

    IMPERSONATE_PROFILES = [
        "chrome120", "chrome119", "chrome118",
        "chrome116", "chrome110", "edge101",
    ]

    def __init__(
        self,
        respect_robots: bool = True,
        min_delay: float = 1.0,
        max_delay: float = 4.0,
        max_retries: int = 3,
        verbose: bool = True,
    ):
        self.respect_robots = respect_robots
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.verbose = verbose

        self._profile = random.choice(self.IMPERSONATE_PROFILES)
        self._session = cf_requests.Session(impersonate=self._profile)
        self._ua = random_ua()
        self._robots_cache: dict = {}
        self._last_request_time: float = 0.0
        self._referer: Optional[str] = None

        if self.verbose:
            print(f"[StealthSession] TLS profile: {self._profile}")
            print(f"[StealthSession] User-Agent : {self._ua[:80]}...")

    # ── Internals ─────────────────────────────────────────────────────────────

    def _base_headers(self, url: str) -> dict:
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if not self._referer else "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
        }
        if self._referer:
            headers["Referer"] = self._referer
        return headers

    def _human_delay(self):
        elapsed = time.time() - self._last_request_time
        target = random.uniform(self.min_delay, self.max_delay)
        wait = max(0.0, target - elapsed)
        # Occasional "reading pause"
        if random.random() < 0.15:
            wait += random.uniform(2.0, 6.0)
        if wait > 0 and self.verbose:
            print(f"  ⏱  waiting {wait:.1f}s …")
        time.sleep(wait)
        self._last_request_time = time.time()

    def _check_robots(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            robots_url = f"{base}/robots.txt"
            try:
                resp = self._session.get(
                    robots_url,
                    headers=self._base_headers(robots_url),
                    timeout=10,
                )
                rp = RobotFileParser()
                rp.parse(resp.text.splitlines())
                self._robots_cache[base] = rp
            except Exception:
                # Cannot reach robots.txt — default to allow
                self._robots_cache[base] = None
        rp = self._robots_cache[base]
        if rp is None:
            return True
        return rp.can_fetch(self._ua, url)

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, url: str, params: Optional[dict] = None, **kwargs) -> cf_requests.Response:
        """Fetch a URL with stealth headers, rate limiting, and retries."""
        if not self._check_robots(url):
            raise PermissionError(f"robots.txt disallows: {url}")

        for attempt in range(1, self.max_retries + 1):
            self._human_delay()
            if self.verbose:
                print(f"  GET {url}" + (f" (attempt {attempt})" if attempt > 1 else ""))
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=self._base_headers(url),
                    timeout=30,
                    allow_redirects=True,
                    **kwargs,
                )
                self._referer = resp.url
                if resp.status_code == 429:
                    wait = 30 * attempt
                    print(f"  ⚠  Rate-limited (429). Sleeping {wait}s …")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except cf_requests.RequestsError as exc:
                if attempt == self.max_retries:
                    raise
                backoff = 2 ** attempt + random.uniform(0, 2)
                print(f"  ⚠  Error: {exc}. Retrying in {backoff:.1f}s …")
                time.sleep(backoff)

    def post(self, url: str, data: Optional[dict] = None, json_body=None, **kwargs) -> cf_requests.Response:
        """POST with stealth headers."""
        self._human_delay()
        headers = self._base_headers(url)
        headers.update({
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Origin": f"{urlparse(url).scheme}://{urlparse(url).netloc}",
        })
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return self._session.post(
            url, data=data, json=json_body, headers=headers, timeout=30, **kwargs
        )

    def soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch a URL and return a BeautifulSoup object."""
        resp = self.get(url, **kwargs)
        return BeautifulSoup(resp.text, "lxml")


# ── High-level Scraper ────────────────────────────────────────────────────────
class Scraper:
    """
    Convenient wrapper around StealthSession with helpers for common tasks.
    """

    def __init__(self, **session_kwargs):
        self.session = StealthSession(**session_kwargs)

    def fetch(self, url: str, **kwargs):
        resp = self.session.get(url, **kwargs)
        soup = BeautifulSoup(resp.text, "lxml")
        return resp, soup

    def extract_links(self, url: str, same_domain_only: bool = True) -> list:
        """Return all links found on a page."""
        _, soup = self.fetch(url)
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        links = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"].split("#")[0].strip()
            if not href:
                continue
            full = urljoin(url, href)
            if same_domain_only and not full.startswith(base):
                continue
            if full.startswith("http"):
                links.add(full)
        return sorted(links)

    def extract_text(self, url: str) -> str:
        """Return clean visible text from a page."""
        _, soup = self.fetch(url)
        for tag in soup(["script", "style", "noscript", "head"]):
            tag.decompose()
        return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()

    def extract_table(self, url: str, table_index: int = 0) -> list:
        """Parse the Nth HTML table into a list of row dicts."""
        _, soup = self.fetch(url)
        tables = soup.find_all("table")
        if not tables:
            return []
        table = tables[min(table_index, len(tables) - 1)]
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            if headers and len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
            else:
                rows.append({f"col_{i}": v for i, v in enumerate(cells)})
        return rows

    def extract_metadata(self, url: str) -> dict:
        """Extract page title, meta description, og:tags, etc."""
        _, soup = self.fetch(url)
        meta = {
            "url": url,
            "title": soup.title.string.strip() if soup.title else "",
            "description": "",
            "og_title": "",
            "og_description": "",
            "og_image": "",
            "canonical": "",
        }
        for tag in soup.find_all("meta"):
            name = tag.get("name", "").lower()
            prop = tag.get("property", "").lower()
            content = tag.get("content", "")
            if name == "description":
                meta["description"] = content
            elif prop == "og:title":
                meta["og_title"] = content
            elif prop == "og:description":
                meta["og_description"] = content
            elif prop == "og:image":
                meta["og_image"] = content
        canonical = soup.find("link", rel="canonical")
        if canonical:
            meta["canonical"] = canonical.get("href", "")
        return meta

    def extract_structured(self, url: str, selectors: dict) -> dict:
        """
        Extract data using CSS selectors.

        Example:
            selectors = {
                "title":  "h1",
                "price":  "span.price",
                "rating": "div.rating",
            }
        """
        _, soup = self.fetch(url)
        result = {"url": url}
        for key, selector in selectors.items():
            el = soup.select_one(selector)
            if el is None:
                result[key] = None
            else:
                for attr in ["data-score", "data-value", "content", "href", "src"]:
                    if el.has_attr(attr):
                        result[key] = el[attr]
                        break
                else:
                    result[key] = el.get_text(strip=True)
        return result

    def crawl(self, start_url: str, max_pages: int = 20, url_filter=None) -> list:
        """BFS crawl — returns list of {url, title, text_preview} dicts."""
        visited, queue, results = set(), [start_url], []
        while queue and len(results) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                print(f"\n[crawl] {len(results)+1}/{max_pages}  {url}")
                _, soup = self.fetch(url)
                title = soup.title.string.strip() if soup.title else url
                body = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
                results.append({"url": url, "title": title, "text_preview": body[:300]})
                base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                for a in soup.find_all("a", href=True):
                    full = urljoin(url, a["href"].split("#")[0])
                    if (
                        full.startswith(base)
                        and full not in visited
                        and full not in queue
                        and (url_filter is None or url_filter(full))
                    ):
                        queue.append(full)
            except Exception as exc:
                print(f"  ⚠  Skipped {url}: {exc}")
        return results

    def scrape_list(self, urls: list, selectors: dict) -> list:
        """Scrape a list of URLs using the same CSS selectors."""
        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[scrape_list] {i}/{len(urls)}  {url}")
            try:
                results.append(self.extract_structured(url, selectors))
            except Exception as exc:
                results.append({"url": url, "error": str(exc)})
        return results

    @staticmethod
    def save_json(data, path: str):
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n✅ Saved JSON → {path}")

    @staticmethod
    def save_csv(data: list, path: str):
        if not data:
            print("No data to save.")
            return
        keys = list(data[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)
        print(f"✅ Saved CSV  → {path}")


# ── Usage examples ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── Basic single-page scrape ───────────────────────────────────────────
    scraper = Scraper(
        respect_robots=True,   # set False to skip robots.txt check
        min_delay=1.5,
        max_delay=3.5,
        verbose=True,
    )

    # Example 1: metadata
    # meta = scraper.extract_metadata("https://example.com")

    # Example 2: CSS selector extraction
    # data = scraper.extract_structured(
    #     "https://example.com/product",
    #     selectors={"title": "h1", "price": "span.price"},
    # )

    # Example 3: crawl a whole site
    # results = scraper.crawl("https://example.com", max_pages=30)
    # Scraper.save_json(results, "crawl.json")

    # Example 4: scrape many URLs
    # urls = ["https://example.com/page/1", "https://example.com/page/2"]
    # rows = scraper.scrape_list(urls, {"heading": "h2", "body": "div.content"})
    # Scraper.save_csv(rows, "output.csv")

    print("scraper.py imported successfully. Use the Scraper class in your own script.")
