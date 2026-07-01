"""
social_scrapers.py — Playwright-based scrapers for Twitter, LinkedIn, Amazon
and YouTube (API + comments scraper).

Each scraper launches a real Chromium browser using your existing logged-in
profile so you don't have to log in again inside the script.
"""

import time, random, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Helpers ───────────────────────────────────────────────────────────────────

def _human_delay(a=1.2, b=3.5):
    time.sleep(random.uniform(a, b))

def _scroll_down(page, times=5, pause=1.5):
    for _ in range(times):
        page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        time.sleep(pause + random.uniform(0, 0.8))

def _new_browser(p, headless=False, slow_mo=120):
    """Launch Chromium. headless=False so sites see a real window."""
    return p.chromium.launch(headless=headless, slow_mo=slow_mo,
        args=["--no-sandbox","--disable-blink-features=AutomationControlled"])

def _stealth_context(browser, storage_state=None):
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="America/New_York",
        storage_state=storage_state,
    )
    # Hide webdriver flag
    ctx.add_init_script("""
        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
        window.chrome={runtime:{}};
    """)
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# TWITTER / X
# ══════════════════════════════════════════════════════════════════════════════

def scrape_twitter(
    target: str,          # @handle, hashtag (#foo), or search keyword
    mode: str = "account",# "account" | "hashtag" | "search"
    max_tweets: int = 50,
    session_file: str = "twitter_session.json",
    headless: bool = False,
) -> list[dict]:
    """
    Scrape tweets from a Twitter/X account, hashtag, or keyword search.
    On first run a browser opens so you can log in; the session is saved for
    future runs.
    """
    session_path = Path(session_file)
    results = []

    with sync_playwright() as p:
        browser = _new_browser(p, headless=headless)
        ctx = _stealth_context(browser, str(session_path) if session_path.exists() else None)
        page = ctx.new_page()

        # ── Build URL ──────────────────────────────────────────────────────
        if mode == "account":
            handle = target.lstrip("@")
            url = f"https://x.com/{handle}"
        elif mode == "hashtag":
            tag = target.lstrip("#")
            url = f"https://x.com/hashtag/{tag}"
        else:
            url = f"https://x.com/search?q={target}&src=typed_query&f=live"

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        _human_delay(2, 4)

        # ── Login check ───────────────────────────────────────────────────
        if "login" in page.url or page.query_selector("input[name='text']"):
            print("[Twitter] Not logged in — please log in in the browser window that opened.")
            print("          The session will be saved automatically when you're done.")
            page.wait_for_url("**/home", timeout=120000)
            ctx.storage_state(path=str(session_path))
            print(f"[Twitter] Session saved → {session_path}")
            page.goto(url, wait_until="domcontentloaded")
            _human_delay(2, 4)

        # ── Scrape tweets ─────────────────────────────────────────────────
        seen = set()
        attempts = 0
        while len(results) < max_tweets and attempts < 30:
            attempts += 1
            tweets = page.query_selector_all("article[data-testid='tweet']")
            for tw in tweets:
                try:
                    # Text
                    txt_el = tw.query_selector("div[data-testid='tweetText']")
                    text = txt_el.inner_text() if txt_el else ""
                    # Author
                    user_els = tw.query_selector_all("span")
                    author = ""
                    for el in user_els:
                        t = el.inner_text()
                        if t.startswith("@") and len(t) < 30:
                            author = t; break
                    # Time
                    time_el = tw.query_selector("time")
                    posted  = time_el.get_attribute("datetime") if time_el else ""
                    # Stats
                    def _stat(label):
                        el = tw.query_selector(f"button[data-testid='{label}'] span")
                        return el.inner_text() if el else "0"
                    likes    = _stat("like")
                    replies  = _stat("reply")
                    retweets = _stat("retweet")
                    # Link
                    link_el = tw.query_selector("a[href*='/status/']")
                    link = ("https://x.com" + link_el.get_attribute("href")) if link_el else ""

                    key = text[:80]
                    if key and key not in seen:
                        seen.add(key)
                        results.append({
                            "author": author, "text": text, "posted": posted,
                            "likes": likes, "replies": replies, "retweets": retweets,
                            "link": link,
                        })
                except Exception:
                    pass

            if len(results) >= max_tweets:
                break
            _scroll_down(page, times=3, pause=1.8)

        ctx.storage_state(path=str(session_path))
        browser.close()

    print(f"[Twitter] Collected {len(results)} tweets.")
    return results[:max_tweets]


# ══════════════════════════════════════════════════════════════════════════════
# LINKEDIN
# ══════════════════════════════════════════════════════════════════════════════

def scrape_linkedin_company(
    company_url: str,       # e.g. https://www.linkedin.com/company/anthropic/
    scrape_people: bool = True,
    scrape_posts:  bool = True,
    max_people:    int  = 30,
    max_posts:     int  = 20,
    session_file:  str  = "linkedin_session.json",
    headless:      bool = False,
) -> dict:
    """
    Scrape a LinkedIn company page: overview, people, and recent posts.
    On first run a browser window opens for you to log in.
    """
    session_path = Path(session_file)
    data = {"company_url": company_url, "overview": {}, "people": [], "posts": []}

    with sync_playwright() as p:
        browser = _new_browser(p, headless=headless, slow_mo=150)
        ctx = _stealth_context(browser, str(session_path) if session_path.exists() else None)
        page = ctx.new_page()

        # ── Login check ───────────────────────────────────────────────────
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        _human_delay(2, 4)
        if "login" in page.url or "authwall" in page.url:
            print("[LinkedIn] Not logged in — please log in in the browser window.")
            page.goto("https://www.linkedin.com/login")
            page.wait_for_url("**/feed/**", timeout=180000)
            ctx.storage_state(path=str(session_path))
            print(f"[LinkedIn] Session saved → {session_path}")

        # ── Company overview ──────────────────────────────────────────────
        base = company_url.rstrip("/")
        print(f"[LinkedIn] Scraping overview: {base}/about/")
        page.goto(f"{base}/about/", wait_until="domcontentloaded", timeout=30000)
        _human_delay(2, 4)
        _scroll_down(page, times=3)

        def _txt(sel):
            el = page.query_selector(sel)
            return el.inner_text().strip() if el else ""

        data["overview"] = {
            "name":        _txt("h1"),
            "tagline":     _txt("p.org-top-card-summary__tagline"),
            "about":       _txt("p.break-words"),
            "industry":    _txt("div[data-test-id='about-us__industry'] dd"),
            "size":        _txt("div[data-test-id='about-us__size'] dd"),
            "headquarters":_txt("div[data-test-id='about-us__headquarters'] dd"),
            "founded":     _txt("div[data-test-id='about-us__foundedOn'] dd"),
            "website":     _txt("div[data-test-id='about-us__website'] a"),
            "followers":   _txt("span.org-top-card-summary-info-list__info-item"),
        }

        # ── People ────────────────────────────────────────────────────────
        if scrape_people:
            print(f"[LinkedIn] Scraping people…")
            page.goto(f"{base}/people/", wait_until="domcontentloaded", timeout=30000)
            _human_delay(2, 4)
            seen_people, attempts = set(), 0
            while len(data["people"]) < max_people and attempts < 15:
                attempts += 1
                cards = page.query_selector_all("li.org-people-profile-card__profile-card-spacing")
                for card in cards:
                    try:
                        name_el  = card.query_selector("div.artdeco-entity-lockup__title")
                        role_el  = card.query_selector("div.artdeco-entity-lockup__subtitle")
                        link_el  = card.query_selector("a")
                        name = name_el.inner_text().strip() if name_el else ""
                        role = role_el.inner_text().strip() if role_el else ""
                        link = link_el.get_attribute("href") if link_el else ""
                        if name and name not in seen_people:
                            seen_people.add(name)
                            data["people"].append({"name": name, "role": role, "profile_url": link})
                    except Exception:
                        pass
                if len(data["people"]) >= max_people: break
                _scroll_down(page, times=2, pause=2)

        # ── Posts ─────────────────────────────────────────────────────────
        if scrape_posts:
            print(f"[LinkedIn] Scraping posts…")
            page.goto(f"{base}/posts/", wait_until="domcontentloaded", timeout=30000)
            _human_delay(2, 4)
            seen_posts, attempts = set(), 0
            while len(data["posts"]) < max_posts and attempts < 15:
                attempts += 1
                posts = page.query_selector_all("div.feed-shared-update-v2")
                for post in posts:
                    try:
                        txt_el    = post.query_selector("div.feed-shared-update-v2__description")
                        time_el   = post.query_selector("span.feed-shared-actor__sub-description")
                        react_el  = post.query_selector("span.social-details-social-counts__reactions-count")
                        text  = txt_el.inner_text().strip()   if txt_el   else ""
                        when  = time_el.inner_text().strip()  if time_el  else ""
                        reacts= react_el.inner_text().strip() if react_el else "0"
                        if text and text[:60] not in seen_posts:
                            seen_posts.add(text[:60])
                            data["posts"].append({"text": text, "posted": when, "reactions": reacts})
                    except Exception:
                        pass
                if len(data["posts"]) >= max_posts: break
                _scroll_down(page, times=3, pause=2)

        ctx.storage_state(path=str(session_path))
        browser.close()

    print(f"[LinkedIn] Done — overview, {len(data['people'])} people, {len(data['posts'])} posts.")
    return data


def scrape_linkedin_profile(
    profile_url: str,
    session_file: str = "linkedin_session.json",
    headless: bool = False,
) -> dict:
    """Scrape a single LinkedIn profile."""
    session_path = Path(session_file)
    data = {"url": profile_url}

    with sync_playwright() as p:
        browser = _new_browser(p, headless=headless, slow_mo=150)
        ctx = _stealth_context(browser, str(session_path) if session_path.exists() else None)
        page = ctx.new_page()

        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        _human_delay(2, 3)
        if "login" in page.url or "authwall" in page.url:
            print("[LinkedIn] Please log in first using scrape_linkedin_company().")
            browser.close()
            return data

        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        _human_delay(2, 4)
        _scroll_down(page, times=5, pause=1.5)

        def _txt(sel):
            el = page.query_selector(sel)
            return el.inner_text().strip() if el else ""

        def _all_txt(sel):
            return [e.inner_text().strip() for e in page.query_selector_all(sel) if e.inner_text().strip()]

        data.update({
            "name":       _txt("h1"),
            "headline":   _txt("div.text-body-medium"),
            "location":   _txt("span.text-body-small.inline.t-black--light.break-words"),
            "about":      _txt("div.display-flex.ph5.pv3 span[aria-hidden='true']"),
            "experience": _all_txt("li.artdeco-list__item span[aria-hidden='true']"),
            "education":  _all_txt("li.pvs-list__item--line-separated span[aria-hidden='true']"),
        })

        ctx.storage_state(path=str(session_path))
        browser.close()

    return data


# ══════════════════════════════════════════════════════════════════════════════
# AMAZON
# ══════════════════════════════════════════════════════════════════════════════

def scrape_amazon_reviews(
    product_url: str,
    max_pages: int = 5,
    headless: bool = False,
) -> list[dict]:
    """
    Scrape Amazon product reviews. Handles pagination automatically.
    No login required.
    """
    results = []

    # Extract ASIN from URL
    asin_match = re.search(r"/dp/([A-Z0-9]{10})", product_url)
    if not asin_match:
        asin_match = re.search(r"/product-reviews/([A-Z0-9]{10})", product_url)
    if not asin_match:
        raise ValueError("Could not find Amazon ASIN in URL. Use a product or review page URL.")
    asin = asin_match.group(1)

    with sync_playwright() as p:
        browser = _new_browser(p, headless=headless)
        ctx = _stealth_context(browser)
        page = ctx.new_page()

        for pg in range(1, max_pages + 1):
            url = f"https://www.amazon.com/product-reviews/{asin}?pageNumber={pg}&sortBy=recent"
            print(f"[Amazon] Page {pg}/{max_pages}: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            _human_delay(2, 5)

            # Handle CAPTCHA notice
            if page.query_selector("form[action='/errors/validateCaptcha']"):
                print("[Amazon] CAPTCHA detected — please solve it in the browser window.")
                page.wait_for_selector("div[data-hook='review']", timeout=120000)

            reviews = page.query_selector_all("div[data-hook='review']")
            if not reviews:
                print(f"[Amazon] No reviews found on page {pg}, stopping.")
                break

            for rev in reviews:
                try:
                    def _t(sel): el = rev.query_selector(sel); return el.inner_text().strip() if el else ""
                    stars_el = rev.query_selector("i[data-hook='review-star-rating'] span")
                    results.append({
                        "title":    _t("a[data-hook='review-title'] span:not(.a-icon-alt)"),
                        "rating":   stars_el.inner_text().strip() if stars_el else "",
                        "date":     _t("span[data-hook='review-date']"),
                        "reviewer": _t("span.a-profile-name"),
                        "verified": bool(rev.query_selector("span[data-hook='avp-badge']")),
                        "body":     _t("span[data-hook='review-body'] span"),
                        "helpful":  _t("span[data-hook='helpful-vote-statement']"),
                    })
                except Exception:
                    pass

            _human_delay(2, 4)

        browser.close()

    print(f"[Amazon] Collected {len(results)} reviews.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# YOUTUBE
# ══════════════════════════════════════════════════════════════════════════════

def scrape_youtube_api(
    query: str,               # channel ID, video ID, or search keyword
    mode: str = "search",     # "search" | "channel" | "video"
    api_key: str = "",
    max_results: int = 50,
) -> list[dict]:
    """
    Pull YouTube data via the free Google API (10,000 req/day free).
    Get a key at: console.cloud.google.com → YouTube Data API v3
    """
    if not api_key:
        raise ValueError("YouTube API key required. Get one free at console.cloud.google.com")

    import urllib.request, urllib.parse

    def _get(url):
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())

    results = []

    if mode == "search":
        params = urllib.parse.urlencode({
            "part": "snippet", "q": query, "type": "video",
            "maxResults": min(max_results, 50), "key": api_key,
        })
        data = _get(f"https://www.googleapis.com/youtube/v3/search?{params}")
        for item in data.get("items", []):
            s = item["snippet"]
            results.append({
                "video_id":    item["id"].get("videoId",""),
                "title":       s.get("title",""),
                "channel":     s.get("channelTitle",""),
                "published":   s.get("publishedAt",""),
                "description": s.get("description","")[:300],
                "thumbnail":   s["thumbnails"]["default"]["url"],
            })

    elif mode == "channel":
        # Get uploads playlist
        params = urllib.parse.urlencode({
            "part": "contentDetails,snippet", "id": query, "key": api_key,
        })
        ch = _get(f"https://www.googleapis.com/youtube/v3/channels?{params}")
        if not ch.get("items"): raise ValueError(f"Channel not found: {query}")
        ch_info   = ch["items"][0]
        uploads   = ch_info["contentDetails"]["relatedPlaylists"]["uploads"]
        ch_name   = ch_info["snippet"]["title"]
        ch_desc   = ch_info["snippet"].get("description","")
        subs_el   = ch_info.get("statistics",{}).get("subscriberCount","")

        # Get videos from uploads playlist
        next_token, fetched = None, 0
        while fetched < max_results:
            p2 = {"part":"snippet","playlistId":uploads,"maxResults":min(50,max_results-fetched),"key":api_key}
            if next_token: p2["pageToken"] = next_token
            vdata = _get(f"https://www.googleapis.com/youtube/v3/playlistItems?{urllib.parse.urlencode(p2)}")
            for item in vdata.get("items", []):
                s = item["snippet"]
                results.append({
                    "channel":     ch_name,
                    "video_id":    s["resourceId"]["videoId"],
                    "title":       s.get("title",""),
                    "published":   s.get("publishedAt",""),
                    "description": s.get("description","")[:300],
                })
                fetched += 1
            next_token = vdata.get("nextPageToken")
            if not next_token: break

    elif mode == "video":
        params = urllib.parse.urlencode({
            "part":"snippet,statistics","id":query,"key":api_key,
        })
        vdata = _get(f"https://www.googleapis.com/youtube/v3/videos?{params}")
        if not vdata.get("items"): raise ValueError(f"Video not found: {query}")
        item = vdata["items"][0]; s = item["snippet"]; st = item.get("statistics",{})
        results.append({
            "title":       s.get("title",""),
            "channel":     s.get("channelTitle",""),
            "published":   s.get("publishedAt",""),
            "description": s.get("description","")[:500],
            "views":       st.get("viewCount",""),
            "likes":       st.get("likeCount",""),
            "comments":    st.get("commentCount",""),
            "tags":        ", ".join(s.get("tags",[])),
        })

    return results


def scrape_youtube_comments(
    video_url: str,
    max_comments: int = 100,
    headless: bool = False,
) -> list[dict]:
    """
    Scrape YouTube comments using Playwright (no API key needed).
    """
    results = []
    with sync_playwright() as p:
        browser = _new_browser(p, headless=headless)
        ctx     = _stealth_context(browser)
        page    = ctx.new_page()

        print(f"[YouTube] Loading {video_url}")
        page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        _human_delay(3, 5)

        # Scroll to load comments
        _scroll_down(page, times=3, pause=2)

        seen, attempts = set(), 0
        while len(results) < max_comments and attempts < 25:
            attempts += 1
            comment_els = page.query_selector_all("ytd-comment-thread-renderer")
            for el in comment_els:
                try:
                    author_el  = el.query_selector("span#author-text")
                    body_el    = el.query_selector("yt-formatted-string#content-text")
                    likes_el   = el.query_selector("span#vote-count-middle")
                    time_el    = el.query_selector("yt-formatted-string.published-time-text a")
                    author = author_el.inner_text().strip() if author_el else ""
                    body   = body_el.inner_text().strip()   if body_el   else ""
                    likes  = likes_el.inner_text().strip()  if likes_el  else "0"
                    when   = time_el.inner_text().strip()   if time_el   else ""
                    key = body[:60]
                    if key and key not in seen:
                        seen.add(key)
                        results.append({"author":author,"comment":body,"likes":likes,"posted":when})
                except Exception:
                    pass
            if len(results) >= max_comments: break
            _scroll_down(page, times=2, pause=2.5)

        browser.close()
    print(f"[YouTube] Collected {len(results)} comments.")
    return results[:max_comments]


# ══════════════════════════════════════════════════════════════════════════════
# G2
# ══════════════════════════════════════════════════════════════════════════════

def scrape_g2_reviews(
    g2_url: str,            # e.g. https://www.g2.com/products/notion/reviews
    max_pages: int = 5,
    headless: bool = False,
) -> list[dict]:
    """
    Scrape G2 reviews using a real browser to bypass their 403 protection.
    No login required — reviews are publicly visible.
    """
    results = []

    # Normalise URL to reviews page
    if g2_url and "/reviews" not in g2_url:
        g2_url = g2_url.rstrip("/") + "/reviews"

    with sync_playwright() as p:
        browser = _new_browser(p, headless=headless, slow_mo=100)
        ctx     = _stealth_context(browser)
        page    = ctx.new_page()

        for pg in range(1, max_pages + 1):
            url = g2_url if pg == 1 else f"{g2_url}?page={pg}"
            print(f"[G2] Page {pg}/{max_pages}: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            _human_delay(2, 5)
            _scroll_down(page, times=4, pause=1.5)

            cards = page.query_selector_all("div[id^='review-']")
            if not cards:
                # Try alternate selector
                cards = page.query_selector_all("div.paper.paper--white.paper--box")
            if not cards:
                print(f"[G2] No reviews found on page {pg}, stopping.")
                break

            for card in cards:
                try:
                    def _t(sel):
                        el = card.query_selector(sel)
                        return el.inner_text().strip() if el else ""

                    # Star rating — count filled stars
                    stars_els = card.query_selector_all("span[class*='stars-full']")
                    rating = ""
                    rating_el = card.query_selector("span.fw-semibold")
                    if rating_el:
                        rating = rating_el.inner_text().strip()

                    # Review title
                    title_el = card.query_selector("h3") or card.query_selector("a.pjax")
                    title = title_el.inner_text().strip() if title_el else ""

                    # Reviewer info
                    name_el = card.query_selector("span.fw-semibold.link-color-blue") or \
                              card.query_selector("a[href*='/users/']")
                    name = name_el.inner_text().strip() if name_el else "Anonymous"

                    role_el = card.query_selector("div.mt-4th") or \
                              card.query_selector("span[class*='text-small']")
                    role = role_el.inner_text().strip() if role_el else ""

                    # Pros and cons
                    pros_el = card.query_selector("div[data-test='pros'] p") or \
                              card.query_selector("div.review-answer p")
                    cons_els = card.query_selector_all("div[data-test='cons'] p")
                    all_answers = card.query_selector_all(".review-answer p")

                    pros = pros_el.inner_text().strip() if pros_el else ""
                    cons = cons_els[0].inner_text().strip() if cons_els else ""

                    # Fallback: grab all answer paragraphs
                    if not pros and all_answers:
                        pros = all_answers[0].inner_text().strip() if len(all_answers) > 0 else ""
                        cons = all_answers[1].inner_text().strip() if len(all_answers) > 1 else ""

                    # Date
                    date_el = card.query_selector("time") or card.query_selector("span[class*='text-small.color-mid']")
                    date = date_el.get_attribute("datetime") or date_el.inner_text().strip() if date_el else ""

                    if title or pros:
                        results.append({
                            "reviewer":  name,
                            "role":      role,
                            "rating":    rating,
                            "title":     title,
                            "pros":      pros,
                            "cons":      cons,
                            "date":      date,
                        })
                except Exception:
                    pass

            _human_delay(2, 4)

            # Check if there's a next page
            next_btn = page.query_selector("a[data-next-page]") or \
                       page.query_selector("li.next a") or \
                       page.query_selector("a[aria-label='Next page']")
            if not next_btn and pg < max_pages:
                print(f"[G2] No next page found after page {pg}.")
                break

        browser.close()

    print(f"[G2] Collected {len(results)} reviews.")
    return results


def scrape_g2_reviews_logged_in(
    g2_url: str,
    max_pages: int = 5,
    session_file: str = "g2_session.json",
    headless: bool = False,
) -> list[dict]:
    """
    Scrape G2 reviews while logged in — bypasses 403 errors.
    Browser opens on first run so you can log in. Session is saved automatically.
    """
    results = []
    session_path = Path(session_file)

    if "/reviews" not in g2_url:
        g2_url = g2_url.rstrip("/") + "/reviews"

    with sync_playwright() as p:
        browser = _new_browser(p, headless=headless, slow_mo=120)
        ctx = _stealth_context(browser, str(session_path) if session_path.exists() else None)
        page = ctx.new_page()

        # ── Login check ───────────────────────────────────────────────────
        print("[G2] Checking login status…")
        page.goto("https://www.g2.com", wait_until="domcontentloaded", timeout=30000)
        _human_delay(2, 4)

        # If not logged in, send to login page
        login_btn = page.query_selector("a[href*='/session/new']") or \
                    page.query_selector("a[data-track*='sign-in']")
        if login_btn:
            print("[G2] Not logged in — please log in in the browser window that opened.")
            print("     The session will be saved automatically when you're done.")
            page.goto("https://www.g2.com/session/new", wait_until="domcontentloaded")
            # Wait until logged in (user menu appears)
            page.wait_for_selector("div[data-dropdown='user-menu'], a[href*='/profile']", timeout=120000)
            ctx.storage_state(path=str(session_path))
            print(f"[G2] Session saved → {session_path}")

        # ── Scrape reviews ────────────────────────────────────────────────
        for pg in range(1, max_pages + 1):
            url = g2_url if pg == 1 else f"{g2_url}?page={pg}"
            print(f"[G2] Page {pg}/{max_pages}: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            _human_delay(2, 5)
            _scroll_down(page, times=4, pause=1.5)

            cards = page.query_selector_all("div[id^='review-']")
            if not cards:
                cards = page.query_selector_all("div.paper.paper--white.paper--box")
            if not cards:
                print(f"[G2] No reviews found on page {pg}, stopping.")
                break

            for card in cards:
                try:
                    def _t(sel):
                        el = card.query_selector(sel)
                        return el.inner_text().strip() if el else ""

                    rating_el = card.query_selector("span.fw-semibold")
                    rating = rating_el.inner_text().strip() if rating_el else ""

                    title_el = card.query_selector("h3") or card.query_selector("a.pjax")
                    title = title_el.inner_text().strip() if title_el else ""

                    name_el = card.query_selector("span.fw-semibold.link-color-blue") or \
                              card.query_selector("a[href*='/users/']")
                    name = name_el.inner_text().strip() if name_el else "Anonymous"

                    role_el = card.query_selector("div.mt-4th") or \
                              card.query_selector("span[class*='text-small']")
                    role = role_el.inner_text().strip() if role_el else ""

                    pros_el  = card.query_selector("div[data-test='pros'] p") or \
                               card.query_selector("div.review-answer p")
                    cons_els = card.query_selector_all("div[data-test='cons'] p")
                    all_ans  = card.query_selector_all(".review-answer p")

                    pros = pros_el.inner_text().strip() if pros_el else ""
                    cons = cons_els[0].inner_text().strip() if cons_els else ""
                    if not pros and all_ans:
                        pros = all_ans[0].inner_text().strip() if len(all_ans) > 0 else ""
                        cons = all_ans[1].inner_text().strip() if len(all_ans) > 1 else ""

                    date_el = card.query_selector("time")
                    date = date_el.get_attribute("datetime") if date_el else ""

                    if title or pros:
                        results.append({
                            "reviewer": name, "role": role, "rating": rating,
                            "title": title, "pros": pros, "cons": cons, "date": date,
                        })
                except Exception:
                    pass

            _human_delay(2, 4)

            next_btn = page.query_selector("a[data-next-page]") or \
                       page.query_selector("li.next a") or \
                       page.query_selector("a[aria-label='Next page']")
            if not next_btn and pg < max_pages:
                break

        ctx.storage_state(path=str(session_path))
        browser.close()

    print(f"[G2] Collected {len(results)} reviews.")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# G2 — REAL CHROME PROFILE
# ══════════════════════════════════════════════════════════════════════════════

def scrape_g2_with_real_chrome(
    g2_url: str,
    max_pages: int = 5,
    profile_dir: str = "g2_chrome_profile",
) -> list[dict]:
    """
    Scrape G2 using a dedicated Chrome profile stored in the scraper folder.
    On first run a Chrome window opens — log in to G2 there.
    Session is saved so you never need to log in again.
    Your normal Chrome stays open the whole time!
    """
    import platform, shutil

    results = []

    if "/reviews" not in g2_url:
        g2_url = g2_url.rstrip("/") + "/reviews"

    # Store a dedicated Chrome profile next to the script
    profile_path = Path(__file__).parent / profile_dir
    profile_path.mkdir(exist_ok=True)
    first_run = not (profile_path / "Default" / "Cookies").exists()

    print(f"[G2] Using dedicated G2 Chrome profile at: {profile_path}")
    if first_run:
        print("[G2] First run — a Chrome window will open. Log in to G2, then close it.")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            channel="chrome",
            headless=False,
            slow_mo=150,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
            ignore_default_args=["--enable-automation"],
        )

        page = ctx.new_page()

        # Remove automation flags
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)

        for pg in range(1, max_pages + 1):
            url = g2_url if pg == 1 else f"{g2_url}?page={pg}"
            print(f"[G2] Page {pg}/{max_pages}: {url}")

            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            _human_delay(3, 6)
            _scroll_down(page, times=4, pause=2.0)

            # Check if blocked
            if "temporarily restricted" in page.content().lower() or \
               "access denied" in page.content().lower():
                print("[G2] ⚠️  Still getting blocked — make sure you're logged in to G2 in Chrome and Chrome was fully closed before running.")
                break

            # G2 uses <article itemprop="review"> for each review card
            cards = page.query_selector_all("article[itemprop='review']")
            if not cards:
                body = page.inner_text("body")
                print(f"[G2] Could not find review cards. Page preview: {body[:300]}")
                break

            for card in cards:
                try:
                    def _t(sel):
                        el = card.query_selector(sel)
                        return el.inner_text().strip() if el else ""

                    # Reviewer name
                    name = (
                        _t("[itemprop='author'] [itemprop='name']") or
                        _t("[itemprop='author']") or
                        _t("div[itemprop='name']") or
                        "Anonymous"
                    )

                    # Role / company size
                    role = (
                        _t("[class*='elv-text-sm']") or
                        _t("div.mt-4th") or
                        ""
                    )

                    # Star rating
                    rating_el = card.query_selector("[itemprop='reviewRating'] [itemprop='ratingValue']")
                    if not rating_el:
                        rating_el = card.query_selector("[itemprop='ratingValue']")
                    rating = rating_el.get_attribute("content") or rating_el.inner_text().strip() if rating_el else ""

                    # Review title — the bold heading inside itemprop="name"
                    title_el = card.query_selector("[itemprop='name'] div")
                    title = title_el.inner_text().strip() if title_el else _t("h3")

                    # Pros — "What do you like best"
                    # G2 puts Q&A in divs with data-poison containing survey info
                    all_paras = card.query_selector_all("div[class*='elv-'] p, div[class*='formatted'] p")
                    pros = all_paras[0].inner_text().strip() if len(all_paras) > 0 else ""
                    cons = all_paras[1].inner_text().strip() if len(all_paras) > 1 else ""

                    # Date
                    date_el = card.query_selector("time")
                    date = date_el.get_attribute("datetime") or date_el.inner_text().strip() if date_el else ""
                    if not date:
                        # Try data-poison attribute which has published_date
                        import json as _json
                        try:
                            dp = card.get_attribute("data-track-in-viewport-options") or "{}"
                            date = _json.loads(dp).get("published_date", "")
                        except Exception:
                            pass

                    if name or title or pros:
                        results.append({
                            "reviewer": name, "role": role, "rating": rating,
                            "title": title, "pros": pros, "cons": cons, "date": date,
                        })
                except Exception:
                    pass

            _human_delay(2, 5)

            next_btn = (
                page.query_selector("a[data-next-page]") or
                page.query_selector("li.next a") or
                page.query_selector("a[aria-label='Next page']") or
                page.query_selector(".pagination-next a") or
                page.query_selector("a[rel='next']")
            )
            if not next_btn and pg < max_pages:
                break

        ctx.close()

    print(f"[G2] Collected {len(results)} reviews.")
    return results


# G2 — UNDETECTED CHROMEDRIVER (best anti-bot bypass)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_g2_undetected(
    g2_url: str = "",
    max_pages: int = 5,
    profile_dir: str = "g2_uc_profile",
    proxy: str = None,
    use_real_profile: bool = False,
) -> list[dict]:
    """
    Scrape G2 reviews using undetected-chromedriver.
    Patches Chrome at a binary level — much harder for G2 to detect than Playwright.

    use_real_profile=True: uses your actual Chrome profile (full history/cookies/extensions).
    Chrome MUST be fully closed before running in this mode.
    """
    import json as _json
    try:
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        import sys, subprocess
        print("[G2-UC] undetected-chromedriver not found — installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "setuptools", "undetected-chromedriver", "selenium"])
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        print("[G2-UC] Installed successfully ✓")

    if g2_url and "/reviews" not in g2_url:
        g2_url = g2_url.rstrip("/") + "/reviews"

    # Determine which Chrome profile to use
    if use_real_profile:
        import os
        real_profile = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
        if not real_profile.exists():
            real_profile = Path(os.environ.get("APPDATA", "")) / ".." / "Local" / "Google" / "Chrome" / "User Data"
        profile_path = real_profile
        first_run = False
        print(f"[G2-UC] Using REAL Chrome profile: {profile_path}")
        print("[G2-UC] ⚠️  Make sure ALL Chrome windows are closed or this will fail!")
    else:
        profile_path = Path(__file__).parent / profile_dir
        profile_path.mkdir(exist_ok=True)
        first_run = not (profile_path / "Default" / "Cookies").exists()
        print(f"[G2-UC] Using dedicated profile: {profile_path}")
        if first_run:
            print("[G2-UC] First run — log in to G2 when the browser opens, then wait.")

    # Find Chrome executable explicitly (avoid picking up Edge)
    import os as _os
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        _os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    chrome_exe = next((p for p in chrome_paths if _os.path.exists(p)), None)
    if chrome_exe:
        print(f"[G2-UC] Using Chrome at: {chrome_exe}")
    else:
        print("[G2-UC] ⚠️  Could not find Chrome — make sure Google Chrome is installed.")

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    # Extra stealth: realistic window size and language
    options.add_argument("--window-size=1366,768")
    options.add_argument("--lang=en-US")
    if proxy:
        options.add_argument(f"--proxy-server={proxy}")
        print(f"[G2-UC] Using proxy: {proxy}")

    # Auto-detect installed Chrome version so uc downloads the right ChromeDriver
    chrome_version = None
    try:
        import subprocess as _sp, re as _re
        for cmd in [
            r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version',
            r'reg query "HKLM\SOFTWARE\Google\Chrome\BLBeacon" /v version',
            r'reg query "HKLM\SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon" /v version',
        ]:
            try:
                out = _sp.check_output(cmd, shell=True, stderr=_sp.DEVNULL).decode()
                m = _re.search(r"(\d+)\.\d+\.\d+\.\d+", out)
                if m:
                    chrome_version = int(m.group(1))
                    print(f"[G2-UC] Detected Chrome version: {chrome_version}")
                    break
            except Exception:
                continue
    except Exception:
        pass

    driver = uc.Chrome(options=options, headless=False, version_main=chrome_version)
    results = []

    try:
        # ── Manual navigation mode: user browses to the page, scraper extracts ──
        print("[G2-UC] Browser is open.")
        print("[G2-UC] ══════════════════════════════════════════════")
        print(f"[G2-UC] Please navigate to your G2 reviews page in the Chrome window.")
        print(f"[G2-UC] Target URL: {g2_url}")
        print("[G2-UC] Once you can see reviews on screen, come back here.")
        print("[G2-UC] The scraper will start automatically once you are on the right page.")
        print("[G2-UC] ══════════════════════════════════════════════")

        # Wait until the user is on the right G2 reviews page
        for _ in range(120):  # wait up to 10 minutes
            time.sleep(5)
            try:
                current = driver.current_url
                if "g2.com/products" in current and ("review" in current.lower() or "#" in current):
                    print(f"[G2-UC] ✓ Detected reviews page: {current}")
                    print("[G2-UC] Starting data extraction…")
                    time.sleep(2)
                    break
            except Exception:
                pass
        else:
            print("[G2-UC] Timed out waiting for navigation. Attempting anyway…")

        # ── Scrape pages ─────────────────────────────────────────────────────
        # Use the URL the user actually navigated to
        actual_url = driver.current_url.split("?")[0].split("#")[0]
        if not g2_url or g2_url == "/reviews":
            g2_url = actual_url
        if g2_url and "/reviews" not in g2_url:
            g2_url = g2_url.rstrip("/") + "/reviews"

        blocked = False
        cards_on_page = 0
        for pg in range(1, max_pages + 1):
            if pg == 1:
                print(f"[G2-UC] Extracting page 1 from current view…")
                time.sleep(2)
            # Pages 2+ are handled by clicking Next at the end of each page

            # Scroll to load lazy content
            for _ in range(5):
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.7);")
                time.sleep(random.uniform(1.0, 2.5))
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)

            # Check page state
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            except Exception:
                print("[G2-UC] Browser closed unexpectedly — stopping.")
                blocked = True
                break

            # Sign-in wall — pause and wait for user to log in
            if any(x in body_text for x in ("sign in", "log in", "create an account", "join g2")):
                current_url = driver.current_url
                if "session" in current_url or "sign_in" in current_url or "login" in current_url or                    ("g2.com" in current_url and "products" not in current_url):
                    print("[G2-UC] ⚠️  G2 is asking you to sign in.")
                    print("[G2-UC] ➜  Please log in to G2 in the Chrome window.")
                    print("[G2-UC] ➜  The scraper will continue automatically once you're logged in.")
                    for _ in range(60):  # wait up to 5 minutes
                        time.sleep(5)
                        try:
                            new_url = driver.current_url
                            new_body = driver.find_element(By.TAG_NAME, "body").text.lower()
                            if "g2.com/products" in new_url and "sign in" not in new_body:
                                print("[G2-UC] ✓ Logged in — continuing scrape.")
                                # Re-navigate to the page we were trying to reach
                                driver.get(f"{g2_url}?page={pg}")
                                time.sleep(random.uniform(4, 7))
                                body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                                break
                        except Exception:
                            pass
                    else:
                        print("[G2-UC] Login timeout — stopping.")
                        break

            if "temporarily restricted" in body_text or "access denied" in body_text:
                print("[G2-UC] ⚠️  G2 access restricted — stopping.")
                blocked = True
                break

            # Parse review cards
            cards = driver.find_elements(By.CSS_SELECTOR, "article[itemprop='review']")
            cards_on_page = len(cards)
            if not cards:
                print(f"[G2-UC] No review cards found on page {pg}. Stopping.")
                print(f"[G2-UC] Page preview: {body_text[:300]}")
                break

            print(f"[G2-UC] Found {cards_on_page} review cards on page {pg}.")

            for card in cards:
                try:
                    def _t(sel):
                        try:
                            return card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        except Exception:
                            return ""

                    def _attr(sel, attr):
                        try:
                            return card.find_element(By.CSS_SELECTOR, sel).get_attribute(attr) or ""
                        except Exception:
                            return ""

                    # Reviewer name
                    name = (
                        _t("[itemprop='author'] [itemprop='name']") or
                        _t("[itemprop='author']") or
                        "Anonymous"
                    )

                    # Role / company size
                    role = _t("[class*='elv-text-sm']") or _t("div.mt-4th") or ""

                    # Star rating from content attribute
                    rating = (
                        _attr("[itemprop='reviewRating'] [itemprop='ratingValue']", "content") or
                        _attr("[itemprop='ratingValue']", "content") or
                        _t("[itemprop='ratingValue']")
                    )

                    # Review title
                    title = _t("[itemprop='name'] div") or _t("h3") or ""

                    # Pros / Cons — first two <p> tags inside elv- divs
                    paras = card.find_elements(
                        By.CSS_SELECTOR,
                        "div[class*='elv-'] p, div[class*='formatted'] p"
                    )
                    pros = paras[0].text.strip() if len(paras) > 0 else ""
                    cons = paras[1].text.strip() if len(paras) > 1 else ""

                    # Date — try <time> element first, then data attribute on card
                    try:
                        time_el = card.find_element(By.TAG_NAME, "time")
                        date = time_el.get_attribute("datetime") or time_el.text.strip()
                    except Exception:
                        date = ""
                    if not date:
                        try:
                            dp = card.get_attribute("data-track-in-viewport-options") or "{}"
                            date = _json.loads(dp).get("published_date", "")
                        except Exception:
                            pass

                    if name or title or pros:
                        results.append({
                            "reviewer": name, "role": role, "rating": rating,
                            "title": title, "pros": pros, "cons": cons, "date": date,
                        })
                except Exception:
                    pass

            if not cards_on_page:
                print(f"[G2-UC] No reviews found on page {pg}, stopping.")
                break

            # Ask the user to manually go to the next page
            if pg < max_pages:
                print(f"[G2-UC] ──────────────────────────────────────────")
                print(f"[G2-UC] ✅ Page {pg} done! Got {cards_on_page} reviews.")
                print(f"[G2-UC] 👉 Please click the Next Page button in Chrome now.")
                print(f"[G2-UC]    Waiting for you to navigate to page {pg + 1}…")
                print(f"[G2-UC] ──────────────────────────────────────────")

                # Wait for URL to change to next page
                current_url = driver.current_url
                for _ in range(60):  # wait up to 5 minutes
                    time.sleep(3)
                    try:
                        new_url = driver.current_url
                        new_body = driver.find_element(By.TAG_NAME, "body").text.lower()
                        # Moved to a new page (URL changed or page param appeared)
                        if new_url != current_url and "g2.com/products" in new_url:
                            print(f"[G2-UC] ✓ Detected navigation to: {new_url}")
                            time.sleep(2)
                            break
                    except Exception:
                        pass
                else:
                    print(f"[G2-UC] Timed out waiting for next page — stopping.")
                    break

    finally:
        try:
            driver.quit()
        except Exception:
            pass  # browser may have already closed

    print(f"[G2-UC] Collected {len(results)} reviews total.")
    return results
