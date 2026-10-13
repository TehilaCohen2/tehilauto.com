import datetime as dt

import config
import content
import mailer
from store import Store
from topics_bank import SEED


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


# ---------- משימה 1: פרומפט לסרטון ----------
PROMPT = """צור סרטון לפי סקיל social-video-nadav עם הפרמטרים הבאים:

סוג: מושן גרפיקס
מסר: {topic}
מילות סגנון: {style}
קול: ללא
ערוץ: וואטסאפ

כללים נוספים (מהסקיל):
- בלי נשים בשום צורה
- פריים 0 מלא ולא ריק
- מיתוג tehilauto במסך סיום
- אנכי 1080x1920, 30fps, 20–30 שניות
- עברית RTL, פונט Heebo
- לשאול על נדב לפני התחלה"""


def task1_prompt(store: Store, force=False):
    if not _guard(store, "task1", force):
        return
    post = next((p for p in store.posts()
                 if not store.is_used(p) and not p.get("תאריך סרטון")), None)
    styles = store.styles()
    if not post or not styles:
        mailer.send_mail("פרומפט סרטון ליום ראשון - אין נושא פנוי",
                         "אין שורה פנויה בטאב פוסטים או סגנונות בגיליון.")
        return
    style = min(styles, key=lambda s: (s["בשימוש_אחרון (תאריך)"] or "0000-00-00", int(s["ID"])))
    body = PROMPT.format(topic=post["נושא"], style=style["שם_סגנון"])
    mailer.send_mail(f"פרומפט סרטון ליום ראשון - {post['נושא']}", body)
    # רק אחרי שהמייל נשלח
    store.mark_style_used(style, config.today())
    store.mark_post_video(post, config.today())  # שפוסט רביעי לא יחזור על אותו נושא


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
