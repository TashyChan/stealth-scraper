"""
Stealth Scraper — Full UI
Run with: python -m streamlit run app.py
"""

import streamlit as st
import json, io, csv, re
from urllib.parse import urlparse

st.set_page_config(page_title="Stealth Scraper", page_icon="🕷️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#0f1117;--surface:#1a1d27;--surface2:#222636;--border:#2e3347;--accent:#6c8bef;--accent2:#a78bfa;--green:#34d399;--red:#f87171;--yellow:#fbbf24;--text:#e2e8f0;--muted:#8892a4;--mono:'JetBrains Mono',monospace;--sans:'Inter',sans-serif;}
html,body,[class*="css"]{font-family:var(--sans)!important;background-color:var(--bg)!important;color:var(--text)!important;}
section[data-testid="stSidebar"]{background-color:var(--surface)!important;border-right:1px solid var(--border);}
section[data-testid="stSidebar"] *{color:var(--text)!important;}
.header-strip{display:flex;align-items:center;gap:14px;padding:24px 0 20px;border-bottom:1px solid var(--border);margin-bottom:28px;}
.header-strip h1{margin:0;font-size:1.75rem;font-weight:700;letter-spacing:-0.02em;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.header-strip p{margin:2px 0 0;color:var(--muted);font-size:0.875rem;}
.stTextInput input,.stTextArea textarea,.stNumberInput input{background:var(--surface2)!important;border:1.5px solid var(--border)!important;border-radius:8px!important;color:var(--text)!important;}
.stButton>button{background:linear-gradient(135deg,var(--accent),var(--accent2))!important;border:none!important;border-radius:8px!important;color:#fff!important;font-weight:600!important;padding:10px 24px!important;}
.result-box{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px;margin-top:16px;}
.result-box h3{margin:0 0 14px;font-size:0.78rem;font-weight:600;color:var(--accent);letter-spacing:.02em;text-transform:uppercase;}
.platform-badge{display:inline-flex;align-items:center;gap:8px;background:var(--surface2);border:1.5px solid var(--border);border-radius:999px;padding:6px 16px;font-size:0.85rem;font-weight:600;margin-bottom:16px;}
.console{background:#0a0c12;border:1px solid var(--border);border-radius:8px;padding:14px 16px;font-family:var(--mono);font-size:0.78rem;line-height:1.7;color:#7dd3a8;max-height:240px;overflow-y:auto;white-space:pre-wrap;}
.tip-box{background:rgba(108,139,239,.08);border:1px solid rgba(108,139,239,.25);border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:0.85rem;}
#MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-strip">
  <div style="font-size:2.4rem">🕷️</div>
  <div><h1>Stealth Scraper</h1><p>Extract data from any website — no code needed</p></div>
</div>
""", unsafe_allow_html=True)

# ── Platform detection ────────────────────────────────────────────────────────
PLATFORM_RULES = [
    ("Reddit","reddit.com","🟠","Posts, comments, subreddits"),
    ("Twitter / X","twitter.com","🐦","Tweets, profiles, threads"),
    ("Twitter / X","x.com","🐦","Tweets, profiles, threads"),
    ("LinkedIn","linkedin.com","💼","Profiles, jobs, company pages"),
    ("YouTube","youtube.com","▶️","Video titles, descriptions, channels"),
    ("Instagram","instagram.com","📸","Posts, reels, profiles"),
    ("Facebook","facebook.com","📘","Posts, pages, groups"),
    ("GitHub","github.com","🐙","Repos, issues, code, profiles"),
    ("Amazon","amazon.com","📦","Products, prices, reviews, ratings"),
    ("eBay","ebay.com","🛒","Listings, prices, seller info"),
    ("Hacker News","news.ycombinator.com","🔶","Stories, comments, scores"),
    ("Wikipedia","wikipedia.org","📖","Articles, references, infoboxes"),
    ("Indeed","indeed.com","💼","Job listings, salaries, companies"),
    ("Glassdoor","glassdoor.com","🏢","Reviews, salaries, interview info"),
    ("G2","g2.com","🟡","Software reviews, ratings, pros & cons"),
    ("Trustpilot","trustpilot.com","⭐","Business reviews, ratings"),
    ("Yelp","yelp.com","⭐","Business reviews, ratings, hours"),
    ("TripAdvisor","tripadvisor.com","✈️","Hotel/restaurant reviews, ratings"),
    ("Zillow","zillow.com","🏠","Property listings, prices, details"),
    ("IMDb","imdb.com","🎬","Movie/TV titles, ratings, cast"),
    ("Medium","medium.com","📝","Articles, authors, claps"),
    ("Substack","substack.com","📧","Newsletter posts, authors"),
    ("Pinterest","pinterest.com","📌","Pins, boards, images"),
    ("TikTok","tiktok.com","🎵","Video info, creators, captions"),
    ("Spotify","spotify.com","🎵","Tracks, artists, albums, playlists"),
    ("Crunchbase","crunchbase.com","💹","Startup info, funding, investors"),
    ("Product Hunt","producthunt.com","😺","Products, upvotes, makers"),
    ("Stack Overflow","stackoverflow.com","💻","Questions, answers, code"),
    ("Airbnb","airbnb.com","🏡","Listings, prices, reviews"),
    ("Booking.com","booking.com","🏨","Hotels, prices, availability"),
    ("News site","reuters.com","📰","Articles, headlines, authors"),
    ("News site","bbc.com","📰","Articles, headlines, authors"),
    ("News site","cnn.com","📰","Articles, headlines, authors"),
    ("News site","nytimes.com","📰","Articles, headlines, authors"),
]

PLATFORM_SELECTORS = {
    "reddit.com":     {"post_title":"h1","score":"div[id*='score']","subreddit":"a[href*='/r/']"},
    "amazon.com":     {"product_name":"#productTitle","price":"span.a-price-whole","rating":"span.a-icon-alt","reviews":"#acrCustomerReviewText"},
    "ebay.com":       {"title":"h1.x-item-title__mainTitle","price":"div.x-price-primary","condition":"div.x-item-condition-text"},
    "github.com":     {"repo_name":"strong[itemprop='name']","description":"p.f4","stars":"#repo-stars-counter-star","language":"span[itemprop='programmingLanguage']"},
    "indeed.com":     {"job_title":"h1.jobsearch-JobInfoHeader-title","company":"div[data-company-name]","location":"div[data-testid='job-location']","salary":"div[id*='salaryInfo']"},
    "yelp.com":       {"business_name":"h1","rating":"div.arrange-unit__373c0__1piwO","address":"address p"},
    "linkedin.com":   {"name":"h1","headline":"div.text-body-medium","company":"span[aria-label*='Current company']"},
    "youtube.com":    {"title":"h1.ytd-video-primary-info-renderer","channel":"yt-formatted-string#owner-name","views":"span.view-count"},
    "imdb.com":       {"title":"h1[data-testid='hero__pageTitle']","rating":"div[data-testid='hero-rating-bar__aggregate-rating__score']"},
    "wikipedia.org":  {"title":"h1#firstHeading","intro":"div.mw-parser-output > p:not(.mw-empty-elt)"},
    "g2.com":         {"reviewer_name":"span[itemprop='author']","rating":"div[itemprop='ratingValue']","review_title":"h3","pros":"div[data-pros]","cons":"div[data-cons]","review_body":"div[itemprop='reviewBody']","reviewer_role":"div.mt-4th"},
    "trustpilot.com": {"business":"h1","score":"p.typography_body-l__KUYFJ","reviews":"p[data-reviews-count-typography]"},
}

def detect_platform(url):
    domain = urlparse(url).netloc.lower().replace("www.","")
    for name,pattern,icon,data_types in PLATFORM_RULES:
        if pattern in domain:
            return {"name":name,"icon":icon,"data_types":data_types,"domain":domain,"suggested_selectors":PLATFORM_SELECTORS.get(pattern,{})}
    return {"name":"General Website","icon":"🌐","data_types":"HTML content, links, text, tables","domain":domain,"suggested_selectors":{}}

def show_platform_badge(url):
    p = detect_platform(url)
    st.markdown(f'<div class="platform-badge"><span>{p["icon"]}</span><span><strong>{p["name"]}</strong> &nbsp;·&nbsp; <span style="color:var(--muted);font-weight:400">{p["data_types"]}</span></span></div>',unsafe_allow_html=True)
    return p

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ General Settings")
    st.markdown("---")
    min_delay      = st.slider("Min delay (s)", 0.5, 5.0, 1.5, 0.5)
    max_delay      = st.slider("Max delay (s)", 1.0, 10.0, 3.5, 0.5)
    max_retries    = st.slider("Retries", 1, 5, 3)
    respect_robots = st.toggle("Respect robots.txt", value=True)
    headless_mode  = st.toggle("Hide browser windows", value=False,
        help="When OFF, you can see the browser and solve CAPTCHAs. Keep OFF until things are working.")
    st.markdown("---")
    st.markdown("### 🔑 API Keys")
    yt_api_key = st.text_input("YouTube Data API key", type="password",
        help="Free at console.cloud.google.com → YouTube Data API v3")
    st.markdown("---")
    st.markdown("### 📊 Google Sheets")

    # ── Persistent storage paths ──────────────────────────────────────────────
    import os as _os
    _cfg_dir  = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".scraper_config")
    _creds_path = _os.path.join(_cfg_dir, "sheets_creds.json")
    _url_path   = _os.path.join(_cfg_dir, "sheets_url.txt")
    _os.makedirs(_cfg_dir, exist_ok=True)

    # ── Auto-load saved credentials on startup ────────────────────────────────
    if "sheets_creds" not in st.session_state and _os.path.exists(_creds_path):
        with open(_creds_path, "rb") as _f:
            st.session_state["sheets_creds"] = _f.read()
    if "sheets_url" not in st.session_state and _os.path.exists(_url_path):
        with open(_url_path) as _f:
            st.session_state["sheets_url"] = _f.read().strip()

    # ── inline helper (function defined later, can't call it here) ────────────
    _ready = bool(st.session_state.get("sheets_creds") and st.session_state.get("sheets_url"))

    # ── Show status ───────────────────────────────────────────────────────────
    if _ready:
        st.success("✅ Sheets connected (saved)")
        if st.button("🔄 Update credentials", key="sheets_update"):
            st.session_state["_sheets_editing"] = True

    if not _ready or st.session_state.get("_sheets_editing"):
        sheets_json = st.file_uploader(
            "Service account JSON", type=["json"], key="gsheets_json",
            help="Google Cloud Console → Service Accounts → Keys → Add Key → JSON")
        sheets_url = st.text_input(
            "Spreadsheet URL", key="gsheets_url",
            value=st.session_state.get("sheets_url", ""),
            placeholder="https://docs.google.com/spreadsheets/d/...")
        if sheets_json and sheets_url.strip():
            creds_bytes = sheets_json.getvalue()
            st.session_state["sheets_creds"] = creds_bytes
            st.session_state["sheets_url"]   = sheets_url.strip()
            # Save to disk so it persists across restarts
            with open(_creds_path, "wb") as _f: _f.write(creds_bytes)
            with open(_url_path,   "w")  as _f: _f.write(sheets_url.strip())
            st.session_state.pop("_sheets_editing", None)
            st.success("✅ Sheets connected and saved — won't need to re-upload!")
            st.rerun()
        elif sheets_json or sheets_url.strip():
            st.info("Enter both the JSON file and Sheet URL to connect.")
    st.markdown("---")
    st.markdown("⚠️ Always check a site's Terms of Service before scraping.")

# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_resource
def get_scraper():
    import sys, os; sys.path.insert(0, os.path.dirname(__file__))
    from scraper import Scraper
    return Scraper

def make_scraper():
    return get_scraper()(respect_robots=respect_robots, min_delay=min_delay,
                         max_delay=max_delay, max_retries=max_retries, verbose=False)

def to_csv_bytes(data):
    if not data: return b""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(data[0].keys()), extrasaction="ignore")
    w.writeheader(); w.writerows(data)
    return buf.getvalue().encode()

def _sheets_ready():
    return bool(st.session_state.get("sheets_creds") and st.session_state.get("sheets_url"))

def dl_buttons(data, stem, sheet_tab=None):
    show_sheets = _sheets_ready() and sheet_tab is not None
    cols = st.columns(3) if show_sheets else st.columns(2)
    cols[0].download_button("⬇️ CSV",  to_csv_bytes(data), f"{stem}.csv", "text/csv", key=f"csv_{stem}")
    cols[1].download_button("⬇️ JSON", json.dumps(data,indent=2,ensure_ascii=False), f"{stem}.json","application/json", key=f"json_{stem}")
    if show_sheets:
        if cols[2].button("📊 → Sheets", key=f"sh_{stem}"):
            try:
                import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                from sheets_export import connect, export_list
                sp = connect(st.session_state["sheets_creds"], st.session_state["sheets_url"])
                n  = export_list(sp, sheet_tab, data if isinstance(data, list) else [data])
                st.success(f"✅ {n} rows written to **'{sheet_tab}'** tab in your Sheet.")
            except Exception as e:
                st.error(f"Sheets export failed: {e}")

# ── Main tabs ─────────────────────────────────────────────────────────────────
tabs = st.tabs(["🎯 Extract Data", "🕸️ Crawl Site", "📋 Bulk Scrape",
                "🐦 Twitter / X", "💼 LinkedIn", "📦 Amazon Reviews", "▶️ YouTube", "🟡 G2 Reviews"])

# ════════════════════════════════════════════════════════════
# TAB 1 — EXTRACT DATA
# ════════════════════════════════════════════════════════════
def _categorise(pages, base_url):
    """Group URLs by their first path segment."""
    from collections import defaultdict
    cats = defaultdict(list)
    for u in pages:
        path = urlparse(u).path.strip("/")
        seg  = path.split("/")[0] if path else ""
        cats[seg or "home"].append(u)
    # Home first, rest alphabetical
    ordered = {}
    if "home" in cats: ordered["home"] = cats.pop("home")
    for k in sorted(cats): ordered[k] = cats[k]
    return ordered

with tabs[0]:
    st.subheader("🎯 Extract Data")
    st.caption("Find all pages on a site, pick the ones you want, export links as CSV or push content sections to Google Sheets.")

    if not _sheets_ready():
        st.info("📊 Connect Google Sheets in the sidebar to enable content export.")

    cs_site = st.text_input("Site URL", key="cs_site", placeholder="https://example.com")

    if st.button("🔍 Find pages", key="cs_find"):
        if not cs_site.strip():
            st.error("Enter a URL.")
        else:
            with st.spinner("Scanning for pages…"):
                try:
                    links = make_scraper().extract_links(cs_site.strip(), same_domain_only=True)
                    all_pages = [cs_site.strip()] + [l for l in links if l != cs_site.strip()]
                    st.session_state["cs_pages"]    = all_pages
                    st.session_state["cs_selected"] = {u: False for u in all_pages}
                except Exception as e:
                    st.error(f"Could not fetch pages: {e}")

    if st.session_state.get("cs_pages"):
        pages = st.session_state["cs_pages"]
        cats  = _categorise(pages, cs_site)

        st.markdown(f"**{len(pages)} pages found across {len(cats)} categories** — tick the ones you want:")

        # ── Global select / deselect ─────────────────────────────────────────
        ga, gb = st.columns(2)
        if ga.button("✅ Select all",   key="cs_all"):
            st.session_state["cs_selected"] = {u: True  for u in pages}; st.rerun()
        if gb.button("⬜ Deselect all", key="cs_none"):
            st.session_state["cs_selected"] = {u: False for u in pages}; st.rerun()

        # ── Per-category expanders ────────────────────────────────────────────
        for cat, urls in cats.items():
            cat_selected = sum(1 for u in urls if st.session_state["cs_selected"].get(u))
            label = f"📁 {cat}  ({cat_selected}/{len(urls)} selected)"
            with st.expander(label, expanded=False):
                cc1, cc2 = st.columns(2)
                if cc1.button(f"✅ All", key=f"cat_all_{cat}"):
                    for u in urls: st.session_state["cs_selected"][u] = True
                    st.rerun()
                if cc2.button(f"⬜ None", key=f"cat_none_{cat}"):
                    for u in urls: st.session_state["cs_selected"][u] = False
                    st.rerun()
                for u in urls:
                    checked = st.session_state["cs_selected"].get(u, False)
                    st.session_state["cs_selected"][u] = st.checkbox(
                        u, value=checked, key=f"cs_chk_{u}")

        chosen = [u for u in pages if st.session_state["cs_selected"].get(u)]
        st.caption(f"{len(chosen)} of {len(pages)} pages selected")

        if chosen:
            st.markdown("---")
            ea, eb = st.columns(2)

            # ── Export links as CSV ───────────────────────────────────────────
            link_rows = [{"url": u} for u in chosen]
            ea.download_button(
                "⬇️ Download links CSV",
                to_csv_bytes(link_rows),
                "links.csv", "text/csv",
                key="csv_links"
            )

            # ── Export content to Sheets ──────────────────────────────────────
            if _sheets_ready():
                if eb.button(f"📝 Export content to Sheets ({len(chosen)} pages)", key="cs_export"):
                    import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                    from sheets_export import connect, export_content_sections
                    try:
                        sp  = connect(st.session_state["sheets_creds"], st.session_state["sheets_url"])
                        sc  = make_scraper()
                        bar = st.progress(0)
                        results = []
                        for i, u in enumerate(chosen):
                            bar.progress((i+1)/len(chosen), text=f"{i+1}/{len(chosen)}: {u[:60]}")
                            try:
                                _, soup = sc.fetch(u)
                                title_tag = soup.find("title")
                                tab_name  = title_tag.get_text(strip=True) if title_tag else ""
                                if not tab_name:
                                    path = urlparse(u).path.strip("/").replace("/", " › ")
                                    tab_name = path or urlparse(u).netloc
                                tab_name = tab_name[:90]
                                n = export_content_sections(sp, tab_name, soup)
                                results.append((u, tab_name, n, None))
                            except Exception as e:
                                results.append((u, "—", 0, str(e)))
                        bar.progress(1.0, text="Done!")
                        ok  = [(u,t,n) for u,t,n,e in results if e is None]
                        err = [(u,e)   for u,t,n,e in results if e]
                        if ok:
                            lines = "\n".join(f"• **{t}** — {n} sections" for _,t,n in ok)
                            st.success(f"✅ Exported {len(ok)} page(s):\n{lines}")
                        for u, e in err:
                            st.warning(f"⚠️ Failed: `{u}` — {e}")
                    except Exception as e:
                        st.error(f"Sheets connection failed: {e}")
            else:
                eb.info("Connect Sheets in sidebar to export content.")

# ════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("🕸️ Crawl Site")
    url=st.text_input("Start URL",placeholder="https://example.com",key="crawl_url")
    if url.strip(): show_platform_badge(url)
    max_pages=st.slider("Max pages",5,100,20)
    must_contain=st.text_input("Only URLs containing (optional)",placeholder="/blog/ or /products/")
    if st.button("▶  Start Crawl"):
        if not url.strip(): st.error("Enter a URL.")
        else:
            from urllib.parse import urljoin
            pb=st.progress(0); log_ph=st.empty(); log=[]; results=[]; visited=set(); queue=[url]
            sc=make_scraper()
            while queue and len(results)<max_pages:
                cur=queue.pop(0)
                if cur in visited: continue
                visited.add(cur)
                pb.progress(len(results)/max_pages,text=f"Page {len(results)+1}/{max_pages}…")
                log.append(f"→ {cur}"); log_ph.markdown(f'<div class="console">{"<br>".join(log[-12:])}</div>',unsafe_allow_html=True)
                try:
                    _,soup=sc.fetch(cur)
                    title=soup.title.string.strip() if soup.title else cur
                    body=re.sub(r"\s+"," ",soup.get_text(separator=" ")).strip()
                    results.append({"url":cur,"title":title,"preview":body[:200]})
                    base=f"{urlparse(cur).scheme}://{urlparse(cur).netloc}"
                    for a in soup.find_all("a",href=True):
                        full=urljoin(cur,a["href"].split("#")[0])
                        if full.startswith(base) and full not in visited and full not in queue:
                            if not must_contain.strip() or must_contain.strip() in full: queue.append(full)
                except Exception as e: log.append(f"  ⚠ {e}")
            pb.progress(1.0,text="Done!")
            st.success(f"Visited {len(results)} pages.")
            st.dataframe(results,width="stretch"); dl_buttons(results,"crawl", sheet_tab="Crawl Site")

# ════════════════════════════════════════════════════════════
# TAB 4 — BULK SCRAPE
# ════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("📋 Bulk Scrape")
    urls_raw=st.text_area("URLs (one per line)",placeholder="https://example.com/1\nhttps://example.com/2",height=130)
    first_url=next((u.strip() for u in urls_raw.splitlines() if u.strip()),None)
    if first_url:
        p=show_platform_badge(first_url)
        if p["suggested_selectors"] and st.button(f"✨ Auto-fill selectors for {p['name']}",key="bulk_auto"):
            st.session_state.bulk_selectors=[{"name":k,"selector":v} for k,v in p["suggested_selectors"].items()]; st.rerun()
    if "bulk_selectors" not in st.session_state:
        st.session_state.bulk_selectors=[{"name":"heading","selector":"h1"},{"name":"body","selector":"p"}]
    to_del=[]
    for i,row in enumerate(st.session_state.bulk_selectors):
        c1,c2,c3=st.columns([2,3,.5])
        st.session_state.bulk_selectors[i]["name"]=c1.text_input("F",value=row["name"],key=f"bn_{i}",label_visibility="collapsed")
        st.session_state.bulk_selectors[i]["selector"]=c2.text_input("S",value=row["selector"],key=f"bs_{i}",label_visibility="collapsed")
        if c3.button("✕",key=f"bd_{i}"): to_del.append(i)
    for i in reversed(to_del): st.session_state.bulk_selectors.pop(i)
    if st.button("+ Add field",key="badd"): st.session_state.bulk_selectors.append({"name":"","selector":""}); st.rerun()
    if st.button("▶  Scrape All",key="bulk_go"):
        urls=[u.strip() for u in urls_raw.splitlines() if u.strip()]
        sels={r["name"]:r["selector"] for r in st.session_state.bulk_selectors if r["name"] and r["selector"]}
        if not urls: st.error("Paste URLs.")
        elif not sels: st.error("Add fields.")
        else:
            pb=st.progress(0); sc=make_scraper(); results=[]
            for i,u in enumerate(urls):
                pb.progress((i+1)/len(urls),text=f"{i+1}/{len(urls)}: {u[:55]}")
                try: results.append(sc.extract_structured(u,sels))
                except Exception as e: results.append({"url":u,"error":str(e),**{k:None for k in sels}})
            pb.progress(1.0,text="Done!")
            st.success(f"Scraped {len(results)} pages.")
            st.dataframe(results,width="stretch"); dl_buttons(results,"bulk", sheet_tab="Bulk Scrape")

# ════════════════════════════════════════════════════════════
# TAB 5 — TWITTER / X
# ════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("🐦 Twitter / X Scraper")
    st.markdown('<div class="tip-box">A real browser window will open. If you\'re already logged in to Twitter in Chrome, the session will be reused automatically after the first run.</div>', unsafe_allow_html=True)

    tw_mode = st.radio("What to scrape", ["Account tweets", "Hashtag", "Keyword search"], horizontal=True)
    if tw_mode == "Account tweets":
        tw_target = st.text_input("Twitter handle", placeholder="@elonmusk or elonmusk")
        tw_mode_key = "account"
    elif tw_mode == "Hashtag":
        tw_target = st.text_input("Hashtag", placeholder="#AI or AI")
        tw_mode_key = "hashtag"
    else:
        tw_target = st.text_input("Search keyword", placeholder="ChatGPT reviews")
        tw_mode_key = "search"

    tw_max = st.slider("Max tweets to collect", 10, 500, 50)

    if st.button("▶  Start Twitter Scrape", key="tw_go"):
        if not tw_target.strip(): st.error("Enter a handle, hashtag, or keyword.")
        else:
            with st.spinner("Opening browser and scraping… (this may take a minute)"):
                try:
                    import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                    from social_scrapers import scrape_twitter
                    results = scrape_twitter(
                        target=tw_target.strip(),
                        mode=tw_mode_key,
                        max_tweets=tw_max,
                        headless=headless_mode,
                    )
                    st.success(f"Collected {len(results)} tweets!")
                    st.dataframe(results, width="stretch")
                    dl_buttons(results, "twitter_results", sheet_tab="Twitter / X")
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.info("Make sure you run: `python -m playwright install chromium` in your terminal first.")

# ════════════════════════════════════════════════════════════
# TAB 6 — LINKEDIN
# ════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("💼 LinkedIn Scraper")
    st.markdown('<div class="tip-box">⚠️ LinkedIn actively monitors for scraping. Use slow delays, a dummy account, and don\'t scrape thousands of profiles at once. The browser will open so you can log in on first use.</div>', unsafe_allow_html=True)

    li_mode = st.radio("What to scrape", ["Company page", "Single profile"], horizontal=True)

    if li_mode == "Company page":
        li_url = st.text_input("Company LinkedIn URL", placeholder="https://www.linkedin.com/company/google/")
        li_people = st.checkbox("Scrape employees", value=True)
        li_posts  = st.checkbox("Scrape recent posts", value=True)
        li_max_p  = st.slider("Max employees", 5, 100, 25)
        li_max_po = st.slider("Max posts", 5, 50, 20)

        if st.button("▶  Scrape Company", key="li_co_go"):
            if not li_url.strip(): st.error("Enter a LinkedIn company URL.")
            else:
                with st.spinner("Opening browser… log in if prompted."):
                    try:
                        import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                        from social_scrapers import scrape_linkedin_company
                        data = scrape_linkedin_company(
                            company_url=li_url.strip(),
                            scrape_people=li_people,
                            scrape_posts=li_posts,
                            max_people=li_max_p,
                            max_posts=li_max_po,
                            headless=headless_mode,
                        )
                        st.success("Done!")
                        st.markdown("**Company Overview**")
                        st.json(data["overview"])
                        if data["people"]:
                            st.markdown(f"**Employees ({len(data['people'])})**")
                            st.dataframe(data["people"], width="stretch")
                            dl_buttons(data["people"], "linkedin_people", sheet_tab="LinkedIn - People")
                        if data["posts"]:
                            st.markdown(f"**Posts ({len(data['posts'])})**")
                            st.dataframe(data["posts"], width="stretch")
                            dl_buttons(data["posts"], "linkedin_posts", sheet_tab="LinkedIn - Posts")
                        st.download_button("⬇️ Full JSON", json.dumps(data,indent=2), "linkedin_company.json","application/json", key="json_li_co")
                        if _sheets_ready():
                            if st.button("📊 Export all to Sheets", key="sh_li_co"):
                                try:
                                    import sys,os; sys.path.insert(0,os.path.dirname(__file__))
                                    from sheets_export import connect, export_linkedin_company
                                    sp = connect(st.session_state["sheets_creds"], st.session_state["sheets_url"])
                                    written = export_linkedin_company(sp, data)
                                    summary = ", ".join(f"**'{k}'** ({v})" for k,v in written.items())
                                    st.success(f"✅ Exported to {summary} in your Sheet.")
                                except Exception as e: st.error(f"Sheets export failed: {e}")
                    except Exception as e:
                        st.error(f"Error: {e}")

    else:
        li_profile = st.text_input("Profile URL", placeholder="https://www.linkedin.com/in/username/")
        if st.button("▶  Scrape Profile", key="li_pr_go"):
            if not li_profile.strip(): st.error("Enter a profile URL.")
            else:
                with st.spinner("Scraping profile…"):
                    try:
                        import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                        from social_scrapers import scrape_linkedin_profile
                        data = scrape_linkedin_profile(li_profile.strip(), headless=headless_mode)
                        st.success("Done!"); st.json(data)
                        st.download_button("⬇️ JSON", json.dumps(data,indent=2), "linkedin_profile.json","application/json")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ════════════════════════════════════════════════════════════
# TAB 7 — AMAZON
# ════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("📦 Amazon Reviews")
    st.caption("Paste any Amazon product page URL — the scraper handles pagination automatically.")
    az_url  = st.text_input("Amazon product URL", placeholder="https://www.amazon.com/dp/B08N5WRWNW")
    az_pages = st.slider("Review pages to scrape (10 reviews each)", 1, 20, 5)

    st.markdown('<div class="tip-box">If a CAPTCHA appears in the browser window, solve it manually — the scraper will continue automatically after.</div>', unsafe_allow_html=True)

    if st.button("▶  Scrape Reviews", key="az_go"):
        if not az_url.strip(): st.error("Enter an Amazon URL.")
        else:
            with st.spinner(f"Scraping up to {az_pages * 10} reviews… browser will open."):
                try:
                    import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                    from social_scrapers import scrape_amazon_reviews
                    results = scrape_amazon_reviews(az_url.strip(), max_pages=az_pages, headless=headless_mode)
                    st.success(f"Collected {len(results)} reviews!")
                    # Summary stats
                    if results:
                        ratings = [r["rating"] for r in results if r.get("rating")]
                        verified = sum(1 for r in results if r.get("verified"))
                        mc1,mc2,mc3 = st.columns(3)
                        mc1.metric("Total reviews", len(results))
                        mc2.metric("Verified purchases", verified)
                        mc3.metric("Most common rating", max(set(ratings),key=ratings.count) if ratings else "—")
                    st.dataframe(results, width="stretch")
                    dl_buttons(results, "amazon_reviews", sheet_tab="Amazon Reviews")
                except ValueError as e: st.error(str(e))
                except Exception as e: st.error(f"Error: {e}")

# ════════════════════════════════════════════════════════════
# TAB 8 — YOUTUBE
# ════════════════════════════════════════════════════════════
with tabs[6]:
    st.subheader("▶️ YouTube Scraper")

    yt_mode = st.radio("What to scrape", ["Search videos", "Channel videos", "Video details", "Video comments"], horizontal=True)

    if yt_mode == "Video comments":
        st.caption("No API key needed — uses browser automation.")
        yt_url = st.text_input("YouTube video URL", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        yt_max = st.slider("Max comments", 20, 500, 100)
        if st.button("▶  Scrape Comments", key="yt_comm_go"):
            if not yt_url.strip(): st.error("Enter a video URL.")
            else:
                with st.spinner("Loading video and scrolling for comments…"):
                    try:
                        import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                        from social_scrapers import scrape_youtube_comments
                        results = scrape_youtube_comments(yt_url.strip(), max_comments=yt_max, headless=headless_mode)
                        st.success(f"Collected {len(results)} comments!")
                        st.dataframe(results, width="stretch")
                        dl_buttons(results, "youtube_comments", sheet_tab="YouTube - Comments")
                    except Exception as e: st.error(f"Error: {e}")
    else:
        st.markdown('<div class="tip-box">🔑 Requires a free YouTube Data API key. Get one at <strong>console.cloud.google.com</strong> → enable <em>YouTube Data API v3</em> → Create credentials → API key. Paste it in the sidebar.</div>', unsafe_allow_html=True)

        if yt_mode == "Search videos":
            yt_query = st.text_input("Search term", placeholder="best AI tools 2025")
            yt_max   = st.slider("Max results", 5, 50, 20)
            if st.button("▶  Search", key="yt_search_go"):
                if not yt_api_key: st.error("Paste your YouTube API key in the sidebar first.")
                elif not yt_query.strip(): st.error("Enter a search term.")
                else:
                    with st.spinner("Searching YouTube…"):
                        try:
                            import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                            from social_scrapers import scrape_youtube_api
                            results = scrape_youtube_api(yt_query.strip(), mode="search", api_key=yt_api_key, max_results=yt_max)
                            st.success(f"Found {len(results)} videos!")
                            st.dataframe(results, width="stretch")
                            dl_buttons(results, "youtube_search", sheet_tab="YouTube - Search")
                        except Exception as e: st.error(f"Error: {e}")

        elif yt_mode == "Channel videos":
            yt_channel = st.text_input("Channel ID", placeholder="UCxxxxxxxxxxxxxxxxxxxxxx",
                help="Find it in the channel URL: youtube.com/channel/UCxxxxxx")
            yt_max = st.slider("Max videos", 5, 200, 50)
            if st.button("▶  Get Channel Videos", key="yt_ch_go"):
                if not yt_api_key: st.error("Paste your YouTube API key in the sidebar first.")
                elif not yt_channel.strip(): st.error("Enter a channel ID.")
                else:
                    with st.spinner("Fetching channel videos…"):
                        try:
                            import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                            from social_scrapers import scrape_youtube_api
                            results = scrape_youtube_api(yt_channel.strip(), mode="channel", api_key=yt_api_key, max_results=yt_max)
                            st.success(f"Found {len(results)} videos!")
                            st.dataframe(results, width="stretch")
                            dl_buttons(results, "youtube_channel", sheet_tab="YouTube - Channel")
                        except Exception as e: st.error(f"Error: {e}")

        elif yt_mode == "Video details":
            yt_vid = st.text_input("Video ID or URL", placeholder="dQw4w9WgXcQ or full URL")
            if st.button("▶  Get Video Details", key="yt_vid_go"):
                if not yt_api_key: st.error("Paste your YouTube API key in the sidebar first.")
                elif not yt_vid.strip(): st.error("Enter a video ID or URL.")
                else:
                    vid_id = yt_vid.strip()
                    match = re.search(r"v=([a-zA-Z0-9_-]{11})", vid_id)
                    if match: vid_id = match.group(1)
                    with st.spinner("Fetching video details…"):
                        try:
                            import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                            from social_scrapers import scrape_youtube_api
                            results = scrape_youtube_api(vid_id, mode="video", api_key=yt_api_key)
                            st.success("Done!")
                            if results: st.json(results[0])
                            dl_buttons(results, "youtube_video", sheet_tab="YouTube - Video")
                        except Exception as e: st.error(f"Error: {e}")

# ════════════════════════════════════════════════════════════
# TAB 9 — G2 REVIEWS
# ════════════════════════════════════════════════════════════
with tabs[7]:
    st.subheader("🟡 G2 Reviews")

    st.markdown(
        '<div class="tip-box">'
        '<b>How to use:</b><br>'
        '1. Set pages below and click <b>▶ Scrape G2 Reviews</b> — a new Chrome window opens<br>'
        '2. In that window, go to your G2 reviews page and wait for reviews to load<br>'
        '3. Scraping starts automatically — when a page is done the terminal says to click Next<br>'
        '4. Click Next yourself in Chrome, scraper picks up the new page automatically<br><br>'
        '✅ Your normal Chrome windows stay open the whole time'
        '</div>',
        unsafe_allow_html=True
    )

    g2_pages = st.slider("Pages to scrape (up to ~10 reviews per page)", 1, 20, 5)

    if st.button("▶  Scrape G2 Reviews", key="g2_go"):
        with st.spinner("Chrome is open — paste your G2 URL in the browser and navigate to the reviews page. Extraction starts automatically once reviews are visible."):
                try:
                    import sys, os; sys.path.insert(0, os.path.dirname(__file__))
                    from social_scrapers import scrape_g2_undetected
                    results = scrape_g2_undetected(
                        max_pages=g2_pages,
                    )
                    if not results:
                        st.warning(
                            "No reviews found. Possible causes:\n"
                            "- G2 is still blocking (IP cooldown needed — wait 30–60 min and retry)\n"
                            "- Review cards have changed structure — check the browser window\n"
                            "- You may need to log in: delete the `g2_uc_profile/` folder and run again"
                        )
                    else:
                        st.success(f"✅ Collected {len(results)} reviews!")
                        ratings = [r["rating"] for r in results if r.get("rating")]
                        mc1, mc2 = st.columns(2)
                        mc1.metric("Total reviews scraped", len(results))
                        mc2.metric("Most common rating", max(set(ratings), key=ratings.count) if ratings else "—")
                        st.dataframe(results, width="stretch")
                        dl_buttons(results, "g2_reviews", sheet_tab="G2 Reviews")

                except ImportError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.info("If you see a ChromeDriver version error, run: `pip install --upgrade undetected-chromedriver`")
