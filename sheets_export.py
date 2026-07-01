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
