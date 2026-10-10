"""סוכן ניטור וצמיחה שבועי ל-tehilauto.com.

שולף נתונים מ-Search Console ומ-GA4, שומר ב-Supabase, משווה לשבוע הקודם
ושולח מייל סיכום בעברית. כל הסודות מגיעים ממשתני סביבה (GitHub Secrets) בלבד.
הסקריפט לא מדפיס נתונים, כתובות או מפתחות ללוג.
"""
import datetime as dt
import html
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from urllib.parse import quote

import requests

# ---- הגדרות (ניתנות לשינוי) ----
LAG_DAYS = 3            # פיגור בין יום ההרצה לסוף טווח הדוח (עיכוב נתוני Search Console)
WINDOW_DAYS = 7
TOP_N = 3
MIN_IMPR_COMPARE = 5    # מינימום חשיפות בשני השבועות כדי להשוות מיקום של ביטוי
OPP_MIN_POS, OPP_MAX_POS = 8, 30
LOW_CTR = 0.01          # "קליקים נמוכים": CTR מתחת ל-1%
LOW_CTR_MIN_IMPR = 20   # ... בביטוי עם לפחות כך וכך חשיפות
GSC_ROW_LIMIT = 1000
TIMEOUT = 60

REQUIRED_ENV = [
    "GOOGLE_SA_JSON", "GA4_PROPERTY_ID", "GSC_SITE", "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD", "MAIL_TO",
]
SOURCES = ["gsc", "ga4_traffic", "ga4_engagement", "ga4_video", "ga4_leads"]

CHANNEL_HE = {
    "Organic Search": "חיפוש אורגני",
    "Direct": "ישיר",
    "Referral": "הפניות מאתרים",
    "Organic Social": "רשתות חברתיות",
    "Paid Social": "רשתות חברתיות (ממומן)",
    "Paid Search": "חיפוש ממומן",
    "Email": "מייל",
    "Unassigned": "לא משויך",
}


class SourceError(Exception):
    """שגיאת מקור נתונים. ההודעה לא כוללת כתובות או סודות."""


def _call(method, url, **kw):
    try:
        r = requests.request(method, url, timeout=TIMEOUT, **kw)
    except requests.RequestException as exc:
        raise SourceError(type(exc).__name__)
    if r.status_code >= 400:
        status = ""
        try:
            err = r.json().get("error", {})
            status = err.get("status", "") if isinstance(err, dict) else ""
        except ValueError:
            pass
        raise SourceError(f"HTTP {r.status_code} {status}".strip())
    return r


# ---- Google ----
def google_token():
    import google.auth.transport.requests
    from google.oauth2 import service_account

    info = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/webmasters.readonly",
            "https://www.googleapis.com/auth/analytics.readonly",
        ],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def fetch_gsc(token, start, end):
    site = quote(os.environ["GSC_SITE"], safe="")
    url = f"https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
    body = {
        "startDate": str(start), "endDate": str(end),
        "dimensions": ["query"], "rowLimit": GSC_ROW_LIMIT,
    }
    r = _call("POST", url, headers={"Authorization": f"Bearer {token}"}, json=body)
    rows = [
        {"query": x["keys"][0], "clicks": x["clicks"], "impressions": x["impressions"],
         "ctr": x["ctr"], "position": x["position"]}
        for x in r.json().get("rows", [])
    ]
    return {"rows": rows}


def ga4_report(token, start, end, body):
    pid = os.environ["GA4_PROPERTY_ID"]
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{pid}:runReport"
    body = {"dateRanges": [{"startDate": str(start), "endDate": str(end)}], **body}
    r = _call("POST", url, headers={"Authorization": f"Bearer {token}"}, json=body)
    out = []
    for row in r.json().get("rows", []):
        dims = [d["value"] for d in row.get("dimensionValues", [])]
        mets = [float(m["value"]) for m in row.get("metricValues", [])]
        out.append((dims, mets))
    return out


def fetch_traffic(token, start, end):
    rows = ga4_report(token, start, end, {
        "dimensions": [{"name": "sessionDefaultChannelGroup"}],
        "metrics": [{"name": "sessions"}],
    })
    channels = {d[0]: int(m[0]) for d, m in rows}
    src_rows = ga4_report(token, start, end, {
        "dimensions": [{"name": "sessionSource"}, {"name": "sessionMedium"}],
        "metrics": [{"name": "sessions"}],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        "limit": 15,
    })
    sources = {f"{d[0]} / {d[1]}": int(m[0]) for d, m in src_rows}
    return {"total_sessions": sum(channels.values()), "channels": channels, "sources": sources}


def fetch_engagement(token, start, end):
    total = ga4_report(token, start, end, {"metrics": [{"name": "averageSessionDuration"}]})
    avg_session = total[0][1][0] if total else None
    pages = ga4_report(token, start, end, {
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "userEngagementDuration"}, {"name": "activeUsers"}],
        "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}],
        "limit": 10,
    })
    page_rows = [
        {"path": d[0], "avg_engagement_sec": (m[0] / m[1]) if m[1] else 0, "users": int(m[1])}
        for d, m in pages
    ]
    return {"avg_session_sec": avg_session, "pages": page_rows}


def fetch_video(token, start, end):
    rows = ga4_report(token, start, end, {
        "dimensions": [
            {"name": "eventName"}, {"name": "customEvent:video_name"},
            {"name": "customEvent:play_type"}, {"name": "customEvent:percent"},
        ],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {
            "fieldName": "eventName",
            "inListFilter": {"values": ["video_play", "video_progress"]},
        }},
    })
    return {"rows": [
        {"event": d[0], "video": d[1], "play_type": d[2], "percent": d[3], "count": int(m[0])}
        for d, m in rows
    ]}


def fetch_leads(token, start, end):
    rows = ga4_report(token, start, end, {
        "dimensions": [{"name": "eventName"}, {"name": "sessionDefaultChannelGroup"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {
            "fieldName": "eventName",
            "stringFilter": {"matchType": "EXACT", "value": "form_submit"},
        }},
    })
    by_channel = {d[1]: int(m[0]) for d, m in rows}
    src_rows = ga4_report(token, start, end, {
        "dimensions": [{"name": "eventName"}, {"name": "sessionSource"}, {"name": "sessionMedium"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {
            "fieldName": "eventName",
            "stringFilter": {"matchType": "EXACT", "value": "form_submit"},
        }},
    })
    by_source = {f"{d[1]} / {d[2]}": int(m[0]) for d, m in src_rows}
    return {"total": sum(by_channel.values()), "by_channel": by_channel, "by_source": by_source}


# ---- Supabase ----
def _sb_headers():
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _sb_url():
    return os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/weekly_raw"


def sb_get(week_start, source):
    r = _call("GET", _sb_url(), headers=_sb_headers(), params={
        "week_start": f"eq.{week_start}", "source": f"eq.{source}", "select": "payload",
    })
    data = r.json()
    return data[0]["payload"] if data else None


def sb_save(week_start, week_end, source, payload):
    headers = {**_sb_headers(), "Content-Type": "application/json",
               "Prefer": "resolution=merge-duplicates,return=minimal"}
    _call("POST", _sb_url(), headers=headers,
          params={"on_conflict": "week_start,source"},
          json=[{"week_start": str(week_start), "week_end": str(week_end),
                 "source": source, "payload": payload}])


# ---- חישובים ----
def compute_queries(cur, prev):
    """מחזיר (עלו, ירדו, הזדמנויות, חשיפות גבוהות וקליקים נמוכים)."""
    rows = cur["rows"] if cur else []
    rises, falls = [], []
    if cur and prev:
        prev_by_q = {r["query"]: r for r in prev["rows"]}
        for r in rows:
            p = prev_by_q.get(r["query"])
            if not p or r["impressions"] < MIN_IMPR_COMPARE or p["impressions"] < MIN_IMPR_COMPARE:
                continue
            delta = p["position"] - r["position"]  # חיובי = שיפור
            item = {**r, "prev_position": p["position"], "delta": delta}
            if delta > 0:
                rises.append(item)
            elif delta < 0:
                falls.append(item)
    rises.sort(key=lambda x: -x["delta"])
    falls.sort(key=lambda x: x["delta"])
    opps = sorted(
        (r for r in rows if OPP_MIN_POS <= r["position"] <= OPP_MAX_POS and r["impressions"] > 0),
        key=lambda x: -x["impressions"])
    low = sorted(
        (r for r in rows if r["impressions"] >= LOW_CTR_MIN_IMPR and r["ctr"] < LOW_CTR),
        key=lambda x: -x["impressions"])
    return rises[:TOP_N], falls[:TOP_N], opps[:TOP_N], low[:TOP_N]


def recommend(opps, low, have_gsc):
    if opps:
        q = opps[0]
        return (f"לחזק בדף את הביטוי «{q['query']}» (מיקום ממוצע {q['position']:.1f}, "
                f"{q['impressions']:.0f} חשיפות), כדי להעלות אותו לעמוד הראשון.")
    if low:
        q = low[0]
        return (f"לשפר כותרת ותיאור סביב הביטוי «{q['query']}» "
                f"({q['impressions']:.0f} חשיפות, {q['clicks']:.0f} קליקים).")
    if not have_gsc:
        return "לבדוק את חיבור Search Console, כי לא התקבלו נתוני חיפוש."
    return "אין מספיק נתונים להמלצה ממוקדת השבוע."


# ---- בניית המייל ----
def e(x):
    return html.escape(str(x))


def fmt_dur(sec):
    m, s = divmod(int(round(sec)), 60)
    return f"{m}:{s:02d}"


def fmt_date(d):
    return d.strftime("%d.%m.%Y")


def change(cur, prev):
    if prev is None:
        return "—"
    if prev == 0:
        return "—" if cur == 0 else "חדש"
    d = (cur - prev) / prev * 100
    arrow = "▲" if d > 0 else "▼" if d < 0 else "▬"
    return f"{arrow} {abs(d):.0f}%"


def src_label(key):
    return "ישיר (מקור לא ידוע)" if key == "(direct) / (none)" else key


def table(headers, rows):
    th = "".join(f"<th style='text-align:right;padding:4px 10px;border-bottom:1px solid #ccc'>{e(h)}</th>"
                 for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td style='padding:4px 10px;border-bottom:1px solid #eee'>{e(c)}</td>"
                         for c in r) + "</tr>" for r in rows)
    return f"<table style='border-collapse:collapse'><tr>{th}</tr>{body}</table>"


def section(title, content):
    return f"<h3 style='margin:18px 0 6px'>{e(title)}</h3>{content}"


def unavailable(errors, source):
    msg = errors.get(source)
    return f"<p>לא זמין{(' (' + e(msg) + ')') if msg else ''}.</p>"


def video_section(cur, prev, errors):
    if cur is None:
        return unavailable(errors, "ga4_video")
    per = {}
    for r in cur["rows"]:
        v = per.setdefault(r["video"], {"click": 0, "hover": 0, "25": 0, "50": 0, "75": 0, "100": 0})
        if r["event"] == "video_play" and r["play_type"] in ("click", "hover"):
            v[r["play_type"]] += r["count"]
        elif r["event"] == "video_progress" and r["percent"] in ("25", "50", "75", "100"):
            v[r["percent"]] += r["count"]
    if not per:
        return "<p>אין עדיין אירועי סרטונים.</p>"
    rows = [[name, v["click"], v["hover"], v["25"], v["50"], v["75"], v["100"]]
            for name, v in sorted(per.items())]
    tot = [sum(v[k] for v in per.values()) for k in ("click", "hover", "25", "50", "75", "100")]
    rows.append(["סה״כ", *tot])
    note = "<p style='font-size:12px;color:#666'>הפעלה בריחוף עשויה לכלול גם הקשה במסך מגע.</p>"
    return table(["סרטון", "הפעלה בלחיצה", "הפעלה בריחוף", "25%", "50%", "75%", "100%"], rows) + note


def build_email(start, end, data, prev, errors):
    have_prev = any(prev.get(s) for s in SOURCES)
    parts = []
    parts.append(f"<h2 style='margin:0'>סיכום שבועי: {fmt_date(start)}–{fmt_date(end)}</h2>")
    if not have_prev:
        parts.append("<p style='background:#fff6d6;padding:6px 10px'>אין עדיין נתוני השוואה "
                     "לשבוע קודם, ולכן לא מוצגים אחוזי שינוי.</p>")

    # 2. כניסות
    t, tp = data.get("ga4_traffic"), prev.get("ga4_traffic")
    if t is None:
        parts.append(section("כניסות לאתר", unavailable(errors, "ga4_traffic")))
    else:
        line = f"<p><b>{t['total_sessions']}</b> כניסות"
        if tp is not None:
            line += f" ({change(t['total_sessions'], tp['total_sessions'])} לעומת השבוע הקודם)"
        parts.append(section("כניסות לאתר", line + "</p>"))
        # 3. מקורות
        rows = []
        for ch, n in sorted(t["channels"].items(), key=lambda kv: -kv[1]):
            row = [CHANNEL_HE.get(ch, ch), n]
            if tp is not None:
                row.append(change(n, tp["channels"].get(ch, 0)))
            rows.append(row)
        hdr = ["מקור", "כניסות"] + (["שינוי"] if tp is not None else [])
        parts.append(section("מאיפה הגיעו", table(hdr, rows) if rows else "<p>אין נתונים.</p>"))

        # 3א. אתר מקור מדויק (מקור / אמצעי)
        sources, sp = t.get("sources", {}), (tp or {}).get("sources")
        srows = []
        for key, n in sorted(sources.items(), key=lambda kv: -kv[1]):
            row = [src_label(key), n]
            if sp is not None:
                row.append(change(n, sp.get(key, 0)))
            srows.append(row)
        shdr = ["מקור / אמצעי", "כניסות"] + (["שינוי"] if sp is not None else [])
        snote = ("<p style='font-size:12px;color:#666'>״ישיר״ כולל גם כניסות מאפליקציות שאינן מעבירות "
                 "מקור (למשל וואטסאפ). קישור עם utm_source מאפשר לזהות אותן.</p>")
        parts.append(section("מאיפה הגיעו: לפי אתר מקור",
                             (table(shdr, srows) + snote) if srows else "<p>אין נתונים.</p>"))

    # 4. זמן שהייה
    g, gp = data.get("ga4_engagement"), prev.get("ga4_engagement")
    if g is None:
        parts.append(section("זמן שהייה ממוצע", unavailable(errors, "ga4_engagement")))
    else:
        if g["avg_session_sec"] is None:
            body = "<p>אין נתונים.</p>"
        else:
            body = f"<p>באתר: <b>{fmt_dur(g['avg_session_sec'])}</b> דקות"
            if gp and gp.get("avg_session_sec") is not None:
                body += f" ({change(g['avg_session_sec'], gp['avg_session_sec'])})"
            body += "</p>"
        if g["pages"]:
            body += table(["דף", "זמן מעורבות ממוצע למשתמש", "משתמשים"],
                          [[p["path"], fmt_dur(p["avg_engagement_sec"]), p["users"]] for p in g["pages"]])
        parts.append(section("זמן שהייה ממוצע", body))

    # 5. סרטונים
    parts.append(section("סרטונים", video_section(data.get("ga4_video"), prev.get("ga4_video"), errors)))

    # 6. פניות
    ld, ldp = data.get("ga4_leads"), prev.get("ga4_leads")
    if ld is None:
        parts.append(section("פניות", unavailable(errors, "ga4_leads")))
    else:
        body = f"<p><b>{ld['total']}</b> פניות"
        if ldp is not None:
            body += f" ({change(ld['total'], ldp['total'])})"
        body += "</p>"
        if ld.get("by_source"):
            body += table(["מקור / אמצעי", "פניות"], [[src_label(k), v]
                                                    for k, v in sorted(ld["by_source"].items(), key=lambda kv: -kv[1])])
        elif ld["by_channel"]:
            body += table(["מקור", "פניות"], [[CHANNEL_HE.get(k, k), v]
                                               for k, v in sorted(ld["by_channel"].items(), key=lambda kv: -kv[1])])
        parts.append(section("פניות", body))

    # 7. ביטויים
    gsc = data.get("gsc")
    rises, falls, opps, low = compute_queries(gsc, prev.get("gsc"))
    if gsc is None:
        parts.append(section("ביטויי חיפוש", unavailable(errors, "gsc")))
    else:
        def pos_rows(items, with_prev):
            if with_prev:
                return [[i["query"], f"{i['prev_position']:.1f} ← {i['position']:.1f}", f"{i['impressions']:.0f}"]
                        for i in items]
            return [[i["query"], f"{i['position']:.1f}", f"{i['impressions']:.0f}", f"{i['clicks']:.0f}"]
                    for i in items]
        body = ""
        if prev.get("gsc") is None:
            body += "<p>עליות וירידות יוצגו כשיהיו נתוני שבוע קודם.</p>"
        else:
            body += "<b>עלו</b>" + (table(["ביטוי", "מיקום", "חשיפות"], pos_rows(rises, True)) if rises else "<p>אין.</p>")
            body += "<b>ירדו</b>" + (table(["ביטוי", "מיקום", "חשיפות"], pos_rows(falls, True)) if falls else "<p>אין.</p>")
        body += "<b>הזדמנויות (מיקום 8–30)</b>" + (
            table(["ביטוי", "מיקום", "חשיפות", "קליקים"], pos_rows(opps, False)) if opps else "<p>אין.</p>")
        body += "<b>חשיפות גבוהות וקליקים נמוכים</b>" + (
            table(["ביטוי", "מיקום", "חשיפות", "קליקים"], pos_rows(low, False)) if low else "<p>אין.</p>")
        parts.append(section("ביטויי חיפוש", body))

    # 8. המלצה
    parts.append(section("פעולה מומלצת לשבוע הבא", f"<p>{e(recommend(opps, low, gsc is not None))}</p>"))

    footer = ["המדידה באתר מתבצעת רק לאחר אישור קוקיז, ולכן המספרים עשויים להיות נמוכים מהתנועה בפועל."]
    if errors.get("supabase"):
        footer.append("שמירת הנתונים ב-Supabase נכשלה השבוע (" + errors["supabase"] + ").")
    parts.append("<p style='font-size:12px;color:#666;margin-top:20px'>" + e(" ".join(footer)) + "</p>")

    return ("<div dir='rtl' style='font-family:Arial,sans-serif;font-size:14px;text-align:right'>"
            + "".join(parts) + "</div>")


def send_mail(subject, html_body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["GMAIL_USER"]
    msg["To"] = os.environ["MAIL_TO"]
    msg.set_content("הדוח השבועי זמין בגרסת HTML.")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as s:
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)


def main():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print("חסרים משתני סביבה (Secrets): " + ", ".join(missing))
        return 1

    end = dt.date.today() - dt.timedelta(days=LAG_DAYS)
    start = end - dt.timedelta(days=WINDOW_DAYS - 1)
    prev_start = start - dt.timedelta(days=WINDOW_DAYS)

    fetchers = {
        "gsc": fetch_gsc, "ga4_traffic": fetch_traffic, "ga4_engagement": fetch_engagement,
        "ga4_video": fetch_video, "ga4_leads": fetch_leads,
    }
    data, prev, errors = {}, {}, {}

    try:
        token = google_token()
    except Exception as exc:  # לא מדפיסים פרטים, כדי לא לחשוף מידע מה-JSON
        print("אימות מול Google נכשל:", type(exc).__name__)
        return 1

    for name, fn in fetchers.items():
        try:
            data[name] = fn(token, start, end)
        except SourceError as exc:
            errors[name] = str(exc)
            print(f"{name}: נכשל ({exc})")
        try:
            prev[name] = sb_get(prev_start, name)
        except SourceError as exc:
            prev[name] = None
            errors["supabase"] = str(exc)

    for name, payload in data.items():
        try:
            sb_save(start, end, name, payload)
        except SourceError as exc:
            errors["supabase"] = str(exc)

    subject = f"סיכום שבועי tehilauto.com: {fmt_date(start)}–{fmt_date(end)}"
    send_mail(subject, build_email(start, end, data, prev, errors))
    print("המייל נשלח.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
