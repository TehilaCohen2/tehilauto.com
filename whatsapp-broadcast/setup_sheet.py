"""הקמת הגיליון "רשימת תפוצה WhatsApp" עם ארבעת הטאבים וטעינת נתונים ראשונית.
אם SPREADSHEET_ID מוגדר: משתמש בגיליון קיים (שיתפי אותו עם חשבון השירות כעורך).
אחרת: יוצר חדש ומשתף עם MAIL_TO."""
import json
import os

import gspread
from google.oauth2.service_account import Credentials

import config
import tasks
from store import SHEET_NAME, TABS, Store


def main():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SA_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    gc = gspread.authorize(creds)
    sid = os.environ.get("SPREADSHEET_ID")
    if sid:
        sh = gc.open_by_key(sid)
    else:
        sh = gc.create(SHEET_NAME)
        sh.share(config.MAIL_TO, perm_type="user", role="writer")
    existing = {w.title: w for w in sh.worksheets()}
    for name, headers in TABS.items():
        ws = existing.get(name) or sh.add_worksheet(name, rows=200, cols=len(headers))
        if not ws.get_all_values():
            ws.append_row(headers)
    if "Sheet1" in existing and not existing["Sheet1"].get_all_values():
        sh.del_worksheet(existing["Sheet1"])
    os.environ["SPREADSHEET_ID"] = sh.id
    tasks.seed(Store(sh))
    print("SPREADSHEET_ID =", sh.id)
    print(sh.url)


if __name__ == "__main__":
    main()
