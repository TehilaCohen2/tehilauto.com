"""שליחה וקריאה של מיילים עם Gmail (smtplib / imaplib + סיסמת אפליקציה)."""
import imaplib
import os
import re
import smtplib
from email import message_from_bytes
from email.message import EmailMessage
from email.utils import make_msgid

from config import MAIL_TO

TIMEOUT = 30


def send_mail(subject, body, to=None):
    """שולח טקסט פשוט. מחזיר את ה-Message-ID."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["GMAIL_USER"]
    msg["To"] = to or MAIL_TO
    msg["Message-ID"] = mid = make_msgid(domain="tehilauto.com")
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as s:
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
    return mid


_APPROVE = re.compile(r"\bAPPROVE\b[\s:]*([0-9][0-9,\s]*)", re.I)
_QUOTE_START = re.compile(r"^(>|On .*wrote:|.*כתב[ה]?:\s*$|-{2,}\s*Original)", re.I)


def parse_approval(text):
    """מחזיר קבוצת מספרים מתשובת APPROVE, מהחלק העליון (לא מהציטוט)."""
    top = []
    for line in text.splitlines():
        if _QUOTE_START.match(line.strip()):
            break
        top.append(line)
    m = _APPROVE.search("\n".join(top))
    if not m:
        return None
    return sorted({int(n) for n in re.findall(r"\d+", m.group(1))})


def _text_of(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", "replace")
        return ""
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")


def fetch_replies(since_date, in_reply_to, sender=None):
    """תשובות מהכתובת של תהילה להודעה עם ה-Message-ID הנתון.
    מחזיר [(message_id, text)]."""
    sender = sender or MAIL_TO
    out = []
    imap = imaplib.IMAP4_SSL("imap.gmail.com", timeout=TIMEOUT)
    try:
        imap.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        imap.select("INBOX", readonly=True)
        since = since_date.strftime("%d-%b-%Y")
        _, data = imap.search(None, f'(FROM "{sender}" SINCE {since})')
        for num in data[0].split():
            _, parts = imap.fetch(num, "(RFC822)")
            msg = message_from_bytes(parts[0][1])
            refs = (msg.get("In-Reply-To", "") + " " + msg.get("References", ""))
            if in_reply_to not in refs:
                continue
            out.append((msg.get("Message-ID", ""), _text_of(msg)))
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return out
