import datetime as dt
import os
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Jerusalem")
MAIL_TO = os.environ.get("MAIL_TO", "tehila21376@gmail.com")
SHEET_NAME = "רשימת תפוצה WhatsApp"


def today() -> str:
    return dt.datetime.now(TZ).date().isoformat()


def now() -> dt.datetime:
    return dt.datetime.now(TZ)
