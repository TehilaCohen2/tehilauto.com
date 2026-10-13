import datetime as dt
import json
import os
import sys

import config
import content
import mailer
from store import Store
from topics_bank import SEED

BRIEF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def _guard(store, name, force):
    """מניעת הרצה כפולה באותו יום (למשל שני טריגרים של שעון קיץ/חורף)."""
    key = f"last_run_{name}"
    if not force and store.get_state(key) == config.today():
        print(f"{name}: כבר רץ היום, מדלג")
        return False
    store.set_state(key, config.today())
    return True


def _video_recent(p, days=7):
    d = p.get("תאריך סרטון")
    if not d:
        return False
    return (config.now().date() - dt.date.fromisoformat(d)).days < days


# ---------- משימה 1: סרטון ----------
def task1_prepare(store: Store, force=False):
    if not _guard(store, "task1", force):
        return
    post = next((p for p in store.posts()
                 if not store.is_used(p) and not p.get("תאריך סרטון")), None)
    styles = store.styles()
    if not post or not styles:
        mailer.send_mail("סרטון שבועי: אין נושא פנוי", "אין שורה פנויה בטאב פוסטים או סגנונות בגיליון.")
        return
    style = min(styles, key=lambda s: (s["בשימוש_אחרון (תאריך)"] or "0000-00-00", int(s["ID"])))
    scenes, direction = content.video_script(post, style["שם_סגנון"])

    lines = [f"נושא: {post['נושא']}", f"סגנון: {style['שם_סגנון']} - {direction}",
             "סוג: מושן גרפיקס | קול: ללא | 1080x1920, 30fps, כ-28 שניות", "",
             "תסריט לאישור:"]
    lines += [f"{i}. [{t}] {k}: {txt}" for i, (t, k, txt) in enumerate(scenes, 1)]
    lines += ["", "כללים: בלי נשים, פריים 0 מלא, מיתוג tehilauto.",
              "לאישור: להריץ ב-Claude Code את הסקיל social-video-nadav עם הקובץ המצורף בתיקיית output,",
              "ובסיום: python broadcast.py video-done"]
    text = "\n".join(lines)

    os.makedirs(BRIEF_DIR, exist_ok=True)
    path = os.path.join(BRIEF_DIR, f"video_brief_{config.today()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")

    mailer.send_mail(f"תסריט סרטון לאישור - {post['נושא']}", text)
    store.mark_post_video(post, config.today())
    store.set_state("video_pending", json.dumps(
        {"post_row": post["_row"], "style_row": style["_row"], "date": config.today()}))
    print("brief:", path)


def video_done(store: Store):
    """אחרי שהסרטון אושר ורונדר: מסמן את הסגנון כבשימוש אחרון."""
    raw = store.get_state("video_pending")
    if not raw:
        print("אין סרטון ממתין")
        return
    pend = json.loads(raw)
    store.mark_style_used({"_row": pend["style_row"]}, config.today())
    store.set_state("video_pending", "")
    print("הסגנון עודכן")


def video_cancel(store: Store):
    """תסריט נדחה: משחרר את הנושא ואת הסגנון לסבב הבא."""
    raw = store.get_state("video_pending")
    if raw:
        pend = json.loads(raw)
        store.t["פוסטים"].set(pend["post_row"], "תאריך סרטון", "")
        store.set_state("video_pending", "")


# ---------- משימה 2: פוסט ----------
def task2_post(store: Store, force=False):
    if not _guard(store, "task2", force):
        return
    post = next((p for p in store.posts()
                 if not store.is_used(p) and not _video_recent(p)), None)
    if not post:
        mailer.send_mail("פוסט WhatsApp ליום רביעי - אין נושא פנוי",
                         "נגמרו הנושאים הפנויים בטאב פוסטים. אשרי נושאים חדשים ממייל מוצאי שבת.")
        return
    text = content.write_post(post["נושא"], post["תיאור"], post.get("קטגוריה", ""),
                              seed=int(post["ID"]))
    mailer.send_mail(f"פוסט WhatsApp ליום רביעי - {post['נושא']}", text)
    store.mark_post_used(post, config.today())  # רק אחרי שהמייל נשלח


# ---------- משימה 3: הצעת נושאים ----------
def task3_propose(store: Store, force=False):
    if not _guard(store, "task3", force):
        return
    for r in store.proposals():  # אצווה ישנה שלא נענתה פגה
        if r["סטטוס"] == "ממתין":
            store.set_proposal_status(r, "פג תוקף")
    names = [p["נושא"] for p in store.posts()] + [r["נושא"] for r in store.proposals()]
    week = config.now().isocalendar()[1]
    picks = content.pick_proposals(names, week)
    if not picks:
        mailer.send_mail("נושאים חדשים לאישור - הבנק התרוקן",
                         "אין עוד נושאים חדשים בקובץ topics_bank.py. יש להוסיף נושאים.")
        return
    batch = config.today()
    lines = []
    for i, (name, desc, cat) in enumerate(picks, 1):
        lines.append(f"{i}. {name} - {desc} (קטגוריה: {cat})")
        store.add_proposal(batch, i, name, desc, cat)
    if len(picks) < 5:
        lines.append(f"\nשימי לב: נשארו רק {len(picks)} נושאים בבנק.")
    lines.append("\nהשב APPROVE + מספרים (לדוגמה: APPROVE 1,3,5) כדי להוסיף לגיליון")
    mid = mailer.send_mail("נושאים חדשים לאישור - רשימת תפוצה WhatsApp", "\n".join(lines))
    store.set_state("pending_batch", batch)
    store.set_state("proposal_msgid", mid)


def check_approvals(store: Store):
    batch = store.get_state("pending_batch")
    mid = store.get_state("proposal_msgid")
    if not batch or not mid:
        return
    processed = set(filter(None, store.get_state("processed_replies").split("|")))
    since = dt.date.fromisoformat(batch)
    for reply_id, text in mailer.fetch_replies(since, mid):
        if reply_id in processed:
            continue
        nums = mailer.parse_approval(text)
        processed.add(reply_id)
        store.set_state("processed_replies", "|".join(sorted(processed)))
        if nums is None:
            continue
        rows = [r for r in store.proposals() if r["אצווה"] == batch and r["סטטוס"] == "ממתין"]
        chosen = [r for r in rows if r["מספר"].isdigit() and int(r["מספר"]) in nums]
        store.add_posts([(r["נושא"], r["תיאור"], r["קטגוריה"]) for r in chosen])
        for r in rows:
            store.set_proposal_status(r, "אושר" if r in chosen else "נדחה")
        store.set_state("pending_batch", "")
        store.set_state("proposal_msgid", "")
        mailer.send_mail("נושאים נוספו לגיליון",
                         "נוספו: " + ", ".join(r["נושא"] for r in chosen) if chosen
                         else "לא נבחרו נושאים.")
        return


def seed(store: Store):
    """טעינה ראשונית של פוסטים וסגנונות."""
    from store import STYLE_NAMES
    if not store.posts():
        store.add_posts(SEED)
    if not store.styles():
        for i, n in enumerate(STYLE_NAMES, 1):
            store.t["סגנונות_סרטון"].append({"ID": i, "שם_סגנון": n, "בשימוש_אחרון (תאריך)": ""})
