# 🕷️ Stealth Scraper

Extract data from any website — no code needed.

---

## ⚡ Quick Start (Do this first)

### Step 1 — Install Python
If you don't have Python installed:
1. Go to **[python.org/downloads](https://python.org/downloads)**
2. Click the big Download button
3. Run the installer
4. ✅ **Check "Add Python to PATH"** on the first screen — this is important!

### Step 2 — Install the Scraper
1. Download this repository as a ZIP (green **Code** button → **Download ZIP**)
2. Unzip it anywhere on your computer (Desktop is fine)
3. Open the folder and **double-click `install.bat`**
4. Wait for it to finish — it installs everything automatically (~5 minutes)

### Step 3 — Run it
**Double-click `run.bat`** — the app opens in your browser automatically.

That's it! You're ready to scrape.

---

## 🗂️ What's Inside

| File | What it does |
|---|---|
| `install.bat` | One-time setup — installs everything |
| `run.bat` | Launch the app (use this every time) |
| `app.py` | The main user interface |
| `scraper.py` | Core scraping engine |
| `social_scrapers.py` | Twitter, LinkedIn, Amazon, G2, YouTube scrapers |

---

## 🔧 Features

### Standard Scraping (works on any website)
| Tab | What it does |
|---|---|
| 🔍 **Quick Scan** | Grab title, description, links and text from any page. Includes a one-click bulk scrape of all found links. |
| 🎯 **Extract Data** | Pull specific fields using CSS selectors. Auto-fills smart selectors for 30+ known sites. |
| 🕸️ **Crawl Site** | Automatically explore all pages on a website starting from one URL. |
| 📋 **Bulk Scrape** | Paste a list of URLs and scrape them all at once into a CSV or JSON file. |

### Social & Platform Scrapers (opens a real browser)
| Tab | What it does |
|---|---|
| 🐦 **Twitter / X** | Scrape tweets from an account, hashtag, or keyword search. Saves your login session. |
| 💼 **LinkedIn** | Scrape company overview, employees, and posts. Or scrape individual profiles. |
| 📦 **Amazon Reviews** | Pull reviews, ratings, and verified purchase status from any product page. |
| ▶️ **YouTube** | Search videos, get channel videos, video details, or scrape comments. |
| 🟡 **G2 Reviews** | Scrape software reviews including pros, cons, ratings, and reviewer roles. |

---

## 🔑 YouTube API Key (Optional)

For YouTube video/channel data (not comments), you need a free API key:

1. Go to **[console.cloud.google.com](https://console.cloud.google.com)**
2. Create a new project
3. Search for **YouTube Data API v3** and enable it
4. Go to **Credentials** → **Create Credentials** → **API Key**
5. Copy the key and paste it in the app's sidebar

Free tier gives you **10,000 requests per day** — more than enough for most use cases.

---

## ⚙️ Settings (in the sidebar)

| Setting | What it does |
|---|---|
| **Min/Max delay** | Time between requests. Higher = slower but less likely to get blocked |
| **Retries** | How many times to retry a failed request |
| **Respect robots.txt** | Recommended on — skips pages sites don't want scraped |
| **Hide browser windows** | Turn ON once everything's working, keep OFF if you need to solve CAPTCHAs |
| **YouTube API key** | Paste your key here |

---

## ❓ Troubleshooting

**"pip is not recognized"**
→ Python isn't installed or "Add to PATH" wasn't checked. Reinstall Python and make sure to check that box.

**"streamlit is not recognized"**
→ Run `install.bat` first, then use `run.bat` to launch (not the terminal directly).

**Getting a 403 error on a site**
→ That site is blocking the basic scraper. Try the platform-specific tab if available (G2, Amazon, etc.) — those use a real browser which is much harder to block.

**LinkedIn/Twitter asking to log in every time**
→ Normal on first use. After you log in, the session is saved and reused automatically.

**CAPTCHA appearing on Amazon**
→ Keep "Hide browser windows" turned OFF so you can solve it manually. The scraper continues automatically after.

**App won't start**
→ Make sure you ran `install.bat` first. If it still fails, open PowerShell, navigate to the folder and run `python -m streamlit run app.py` to see the full error message.

---

## ⚠️ Important Notes

- Always check a website's **Terms of Service** before scraping it
- Use reasonable delays — don't hammer sites with thousands of requests
- LinkedIn actively monitors for scraping — use slow delays and don't scrape thousands of profiles
- Twitter/X may require solving CAPTCHAs occasionally
- This tool is for **personal and research use** — don't use it to collect data for spam or resale

---

## 📦 Built With

- [Streamlit](https://streamlit.io) — UI framework
- [curl-cffi](https://github.com/yifeikong/curl-cffi) — TLS fingerprint spoofing
- [Playwright](https://playwright.dev/python/) — Browser automation
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
- [fake-useragent](https://github.com/fake-useragent/fake-useragent) — User agent rotation
