"""כתיבת התוכן: פוסט וואטסאפ, תסריט סרטון והצעות נושאים. הכול Python טהור."""
import random

from topics_bank import BANK, MISTAKE, TIME, WA

OPENERS = {
    TIME: ["רוצים לחסוך כמה דקות ביום?", "יש טיפ קטן שחוסך זמן בכל יום:", "כמה פעמים ביום אתם עושים את זה ידנית?"],
    WA: ["יש בוואטסאפ ביזנס הגדרה קטנה שעושה סדר:", "לקוחות כותבים לכם בוואטסאפ? זה בשבילכם:", "הגדרה אחת בוואטסאפ ביזנס, שתי דקות:"],
    MISTAKE: ["טעות קטנה שהרבה בעלי עסקים עושים בלי לשים לב:", "גם אתם עושים את זה? זו טעות נפוצה:", "עוצרים רגע, יש כאן טעות שקל לתקן:"],
}
CLOSERS = [
    "נסו היום, זה לוקח פחות מדקה 🙂",
    "תנסו ותספרו לי איך היה 🙌",
    "אם זה עזר, שלחו לעוד בעל עסק שמכירים.",
    "נסו פעם אחת ותרגישו את ההבדל.",
]
MAX_LINES = 5


def _pick(options, seed):
    return options[seed % len(options)]


def write_post(name, desc, category, seed=0):
    """פוסט עד 5 שורות: פתיחה, שם הטיפ, הטיפ, סיום."""
    opener = _pick(OPENERS.get(category, OPENERS[TIME]), seed)
    lines = [opener, f"*{name}*", desc, _pick(CLOSERS, seed)]
    assert len(lines) <= MAX_LINES
    return "\n".join(lines)


def pick_proposals(existing_names, week_number, n=5):
    """5 נושאים מהבנק: 2+2+1 לפי שלוש הקטגוריות, הקטגוריה עם ה-1 מתחלפת
    מדי שבוע. מדלג על נושאים שכבר קיימים בגיליון או בהצעות."""
    taken = {x.strip() for x in existing_names}
    cats = [TIME, WA, MISTAKE]
    quota = {c: 2 for c in cats}
    quota[cats[week_number % 3]] = 1
    chosen = []
    for c in cats:
        pool = [t for t in BANK if t[2] == c and t[0] not in taken]
        chosen += pool[:quota[c]]
    if len(chosen) < n:  # קטגוריה התרוקנה: משלימים מהשאר
        have = {t[0] for t in chosen}
        rest = [t for t in BANK if t[0] not in taken and t[0] not in have]
        chosen += rest[:n - len(chosen)]
    return chosen[:n]
