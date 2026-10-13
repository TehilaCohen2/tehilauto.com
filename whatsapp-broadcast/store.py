"""גישה לגיליון (gspread). כל הטאבים נקראים דרך אובייקט worksheet עם
get_all_values / update_cell / append_row, כך שאפשר להחליף בדמה בבדיקות."""
import json
import os

from config import MAIL_TO, SHEET_NAME

POSTS, STYLES = "פוסטים", "סגנונות_סרטון"
PROPOSALS, STATE = "הצעות_ממתינות", "מצב"

POSTS_H = ["ID", "נושא", "תיאור", "נוצל (כן/לא)", "תאריך שימוש", "קטגוריה", "תאריך סרטון"]
STYLES_H = ["ID", "שם_סגנון", "בשימוש_אחרון (תאריך)"]
PROPOSALS_H = ["אצווה", "מספר", "נושא", "תיאור", "קטגוריה", "סטטוס"]
STATE_H = ["מפתח", "ערך"]
TABS = {POSTS: POSTS_H, STYLES: STYLES_H, PROPOSALS: PROPOSALS_H, STATE: STATE_H}

STYLE_NAMES = ["טיפוגרפיה קינטית", "שרטוט טכני", "אלמנטים בתלת-ממד",
               "תנועת מצלמה רציפה", "גימור קולנועי", "מאץ' קאט"]


def open_spreadsheet():
    import gspread
    from google.oauth2.service_account import Credentials
    info = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets",
                      "https://www.googleapis.com/auth/drive"])
    gc = gspread.authorize(creds)
    sid = os.environ.get("SPREADSHEET_ID")
    if sid:
        return gc.open_by_key(sid)
    return gc.open(SHEET_NAME)


class Tab:
    """עטיפה על worksheet: שורות כמילונים, עם מספר שורה בגיליון."""

    def __init__(self, ws, headers):
        self.ws, self.headers = ws, headers

    def rows(self):
        vals = self.ws.get_all_values()
        if not vals:
            return []
        head = vals[0]
        out = []
        for i, v in enumerate(vals[1:], start=2):
            if not any(c.strip() for c in v):
                continue
            d = {h: (v[j].strip() if j < len(v) else "") for j, h in enumerate(head)}
            d["_row"] = i
            out.append(d)
        return out

    def set(self, row, header, value):
        col = self._col(header)
        self.ws.update_cell(row, col, value)

    def append(self, d):
        self.ws.append_row([d.get(h, "") for h in self.headers],
                           value_input_option="USER_ENTERED")

    def _col(self, header):
        head = self.ws.get_all_values()[0]
        return head.index(header) + 1


class Store:
    def __init__(self, spreadsheet=None, tabs=None):
        if tabs is None:
            spreadsheet = spreadsheet or open_spreadsheet()
            tabs = {n: spreadsheet.worksheet(n) for n in TABS}
        self.t = {n: Tab(tabs[n], TABS[n]) for n in TABS}

    # --- פוסטים ---
    def posts(self):
        return self.t[POSTS].rows()

    @staticmethod
    def is_used(p):
        return p["נוצל (כן/לא)"].strip() == "כן"

    def mark_post_used(self, p, date):
        self.t[POSTS].set(p["_row"], "נוצל (כן/לא)", "כן")
        self.t[POSTS].set(p["_row"], "תאריך שימוש", date)

    def mark_post_video(self, p, date):
        self.t[POSTS].set(p["_row"], "תאריך סרטון", date)

    def add_posts(self, items, start_id=None):
        """items: [(name, desc, category)]. מחזיר את ה-IDs החדשים."""
        ids = [int(p["ID"]) for p in self.posts() if p["ID"].isdigit()]
        nxt = max(ids, default=0) + 1
        new = []
        for name, desc, cat in items:
            self.t[POSTS].append({"ID": nxt, "נושא": name, "תיאור": desc,
                                  "נוצל (כן/לא)": "", "תאריך שימוש": "",
                                  "קטגוריה": cat, "תאריך סרטון": ""})
            new.append(nxt)
            nxt += 1
        return new

    # --- סגנונות ---
    def styles(self):
        return self.t[STYLES].rows()

    def mark_style_used(self, s, date):
        self.t[STYLES].set(s["_row"], "בשימוש_אחרון (תאריך)", date)

    # --- הצעות ---
    def proposals(self):
        return self.t[PROPOSALS].rows()

    def add_proposal(self, batch, num, name, desc, cat):
        self.t[PROPOSALS].append({"אצווה": batch, "מספר": num, "נושא": name,
                                  "תיאור": desc, "קטגוריה": cat, "סטטוס": "ממתין"})

    def set_proposal_status(self, row, status):
        self.t[PROPOSALS].set(row["_row"], "סטטוס", status)

    # --- מצב (key/value) ---
    def get_state(self, key, default=""):
        for r in self.t[STATE].rows():
            if r["מפתח"] == key:
                return r["ערך"]
        return default

    def set_state(self, key, value):
        for r in self.t[STATE].rows():
            if r["מפתח"] == key:
                self.t[STATE].set(r["_row"], "ערך", value)
                return
        self.t[STATE].append({"מפתח": key, "ערך": value})
