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


STYLE_DIRECTION = {
    "טיפוגרפיה קינטית": "מילים עפות, נמתחות ונוחתות בקצב; הכותרת נבנית ממילים נעות.",
    "שרטוט טכני": "עט משרטט בזמן אמת על נייר משבצות; הצעדים מצוירים כתרשים.",
    "אלמנטים בתלת-ממד": "גופים וכותרות על משטח מוטה, עם פרספקטיבה והטיה ועומק.",
    "תנועת מצלמה רציפה": "שוט אחד בלי חיתוך שעובר בין שכבות הסצנה.",
    "גימור קולנועי": "גרעיניות, זוהר, הכהיה בשוליים וטשטוש תנועה.",
    "מאץ' קאט": "מעברים חלקים בין שוטים דרך צורה שמשתנה.",
}


def video_script(post, style):
    """טיוטת תסריט למושן גרפיקס, ללא קול, 28 שניות. פריים 0 מלא."""
    name, desc, cat = post["נושא"], post["תיאור"], post.get("קטגוריה", "")
    if cat == MISTAKE:
        problem = "זו טעות שקל לעשות, ושווה לעצור עליה."
        result = "פחות טעויות, פחות עצבים."
    elif cat == WA:
        problem = "לקוחות כותבים, ואתם עונים אחד אחד."
        result = "יותר סדר, ופחות הודעות שנופלות בין הכיסאות."
    else:
        problem = "עוד פעולה ידנית שחוזרת על עצמה כל יום."
        result = "דקות שחוזרות אליכם בכל יום."
    scenes = [
        ("0:00–0:04", "הוק (פריים 0 מלא)", name),
        ("0:04–0:10", "הבעיה", problem),
        ("0:10–0:19", "הפעולה האחת", desc),
        ("0:19–0:24", "התוצאה", result),
        ("0:24–0:28", "מסך סיום", "לוגו tehilauto, שורת תיאור, כפתור זהב ״כתבו לי בפרטי״, וואטסאפ 053-315-3356"),
    ]
    return scenes, STYLE_DIRECTION.get(style, "")


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
