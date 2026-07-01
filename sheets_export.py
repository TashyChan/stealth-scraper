"""
sheets_export.py — Google Sheets integration for Stealth Scraper

Setup (one-time):
  1. Go to console.cloud.google.com
  2. Create a project → Enable "Google Sheets API" + "Google Drive API"
  3. IAM & Admin → Service Accounts → Create → Download JSON key
  4. Open your Google Sheet → Share with the service account email (editor access)
  5. Upload the JSON key + paste your Sheet URL in the sidebar
"""

import json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Preferred column order per worksheet — defines what shows first
COLUMN_ORDER = {
    "Twitter / X":        ["author", "text", "posted", "likes", "replies", "retweets", "url"],
    "Amazon Reviews":     ["title", "rating", "reviewer", "date", "verified", "text", "url"],
    "YouTube - Comments": ["author", "comment", "likes", "posted"],
    "YouTube - Search":   ["type", "video_id", "title", "channel", "views", "likes", "comments", "published", "description"],
    "YouTube - Channel":  ["type", "video_id", "title", "channel", "views", "likes", "comments", "published", "description"],
    "YouTube - Video":    ["type", "video_id", "title", "channel", "views", "likes", "comments", "published", "description"],
    "G2 Reviews":         ["reviewer", "role", "rating", "title", "pros", "cons", "date"],
    "LinkedIn - People":  ["name", "role", "profile_url"],
    "LinkedIn - Posts":   ["text", "posted", "reactions"],
    "Crawl Site":         ["url", "title", "text_preview"],
    "Quick Scan - Links": ["url"],
    "Bulk Scrape":        ["url"],
}

_HEADER_MAP = {
    "video_id":    "Video ID",
    "profile_url": "Profile URL",
    "text_preview":"Text Preview",
    "url":         "URL",
}

def _to_header(key: str) -> str:
    return _HEADER_MAP.get(key, key.replace("_", " ").title())


def connect(creds_json_bytes: bytes, sheet_url: str):
    """
    Authenticate and open the spreadsheet.
    Returns a gspread Spreadsheet object.
    """
    info = json.loads(creds_json_bytes)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_url(sheet_url)


def _get_or_create_ws(spreadsheet, name: str):
    """Get existing worksheet (and clear it) or create a new one."""
    try:
        ws = spreadsheet.worksheet(name)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=2000, cols=30)
    return ws


def export_list(spreadsheet, tab_name: str, data: list) -> int:
    """
    Write a list of dicts to a worksheet tab.
    Columns are ordered by COLUMN_ORDER[tab_name] if defined,
    then any remaining keys appended after.
    Returns the number of rows written.
    """
    if not data:
        return 0

    # Build ordered key list
    preferred = COLUMN_ORDER.get(tab_name, [])
    all_keys = list(data[0].keys())
    keys = preferred + [k for k in all_keys if k not in preferred]
    # Drop keys that don't appear in any row
    keys = [k for k in keys if any(row.get(k) not in (None, "") for row in data)]

    ws = _get_or_create_ws(spreadsheet, tab_name)

    rows = [[_to_header(k) for k in keys]]
    for row in data:
        rows.append([str(row.get(k, "") or "") for k in keys])

    ws.update(rows, value_input_option="USER_ENTERED")
    return len(data)


def export_single(spreadsheet, tab_name: str, data: dict) -> int:
    """
    Write a single dict as two columns: Field | Value.
    Used for things like a single extracted page or LinkedIn profile.
    """
    if not data:
        return 0
    ws = _get_or_create_ws(spreadsheet, tab_name)
    rows = [["Field", "Value"]] + [[str(k), str(v or "")] for k, v in data.items()]
    ws.update(rows, value_input_option="USER_ENTERED")
    return len(data)


def export_linkedin_company(spreadsheet, data: dict) -> dict:
    """
    LinkedIn company data has nested people + posts.
    Writes up to three tabs: overview, people, posts.
    Returns dict of {tab_name: rows_written}.
    """
    written = {}

    # Overview — flat key/value
    overview = {k: v for k, v in data.items() if k not in ("people", "posts")}
    if overview:
        export_single(spreadsheet, "LinkedIn - Overview", overview)
        written["LinkedIn - Overview"] = len(overview)

    if data.get("people"):
        n = export_list(spreadsheet, "LinkedIn - People", data["people"])
        written["LinkedIn - People"] = n

    if data.get("posts"):
        n = export_list(spreadsheet, "LinkedIn - Posts", data["posts"])
        written["LinkedIn - Posts"] = n

    return written


# ── Content section export ────────────────────────────────────────────────────

_TYPE_LABELS = {
    "h1": "Heading 1", "h2": "Heading 2", "h3": "Heading 3",
    "h4": "Heading 4", "h5": "Heading 5",
    "p":  "Paragraph", "li": "List item",
    "blockquote": "Quote", "figcaption": "Caption",
}

# Light background colors per section type for Google Sheets
_TYPE_COLORS = {
    "Heading 1":  {"red": 0.827, "green": 0.851, "blue": 0.965},  # soft indigo
    "Heading 2":  {"red": 0.851, "green": 0.918, "blue": 0.980},  # soft blue
    "Heading 3":  {"red": 0.878, "green": 0.949, "blue": 0.878},  # soft green
    "Heading 4":  {"red": 0.949, "green": 0.949, "blue": 0.878},  # soft yellow
    "List item":  {"red": 0.961, "green": 0.949, "blue": 0.914},  # soft amber
    "Quote":      {"red": 0.949, "green": 0.914, "blue": 0.961},  # soft purple
}


def export_content_sections(spreadsheet, tab_name: str, soup) -> int:
    """
    Parse a BeautifulSoup object into ordered content sections and export
    to a Google Sheet tab formatted for annotation.

    Columns: # | Type | Content | Your Comments

    Returns the number of sections written.
    """
    # Strip noise
    for tag in soup(["script", "style", "noscript", "nav", "footer",
                     "header", "aside", "form", "iframe"]):
        tag.decompose()

    # Walk the DOM in order — only meaningful content tags
    tags = soup.find_all(["h1","h2","h3","h4","h5","p","li","blockquote","figcaption"])

    sections = []
    seen = set()
    for tag in tags:
        text = tag.get_text(separator=" ", strip=True)
        # Skip blanks, very short noise, and duplicates
        if not text or len(text) < 8 or text in seen:
            continue
        seen.add(text)
        label = _TYPE_LABELS.get(tag.name, tag.name.title())
        sections.append({"num": len(sections) + 1, "type": label, "content": text})

    if not sections:
        return 0

    ws = _get_or_create_ws(spreadsheet, tab_name)

    # Write data
    header = ["#", "Type", "Content", "Your Comments"]
    rows = [header] + [
        [str(s["num"]), s["type"], s["content"], ""]
        for s in sections
    ]
    ws.update(rows, value_input_option="USER_ENTERED")

    # ── Formatting ────────────────────────────────────────────────────────────
    try:
        sheet_id = ws._properties["sheetId"]
        requests = []

        # Freeze header row
        requests.append({
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        })

        # Header row: dark bg + white bold text
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.2, "green": 0.3, "blue": 0.5},
                    "textFormat": {"bold": True, "foregroundColor": {"red":1,"green":1,"blue":1}, "fontSize": 10},
                    "horizontalAlignment": "LEFT",
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        })

        # Color rows by section type (columns A + B only, content stays white)
        for i, s in enumerate(sections):
            color = _TYPE_COLORS.get(s["type"])
            if color:
                row_idx = i + 1  # offset by header
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                            "startColumnIndex": 0, "endColumnIndex": 2,
                        },
                        "cell": {"userEnteredFormat": {"backgroundColor": color}},
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                })

        # Column widths: narrow #, medium Type, wide Content, wide Comments
        widths = [40, 100, 450, 350]
        for col_idx, px in enumerate(widths):
            requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                              "startIndex": col_idx, "endIndex": col_idx + 1},
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            })

        # Wrap text in Content + Comments columns
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1,
                          "startColumnIndex": 2, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.wrapStrategy",
            }
        })

        spreadsheet.batch_update({"requests": requests})

    except Exception:
        pass  # Formatting is best-effort — data is already written

    return len(sections)
