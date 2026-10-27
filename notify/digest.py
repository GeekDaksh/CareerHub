"""Morning email: the best new gigs, two startups to email, one AI platform to apply to.
Sent once a day by the gig workflow (first run after DIGEST_HOUR_IST). Needs GMAIL_ADDRESS + GMAIL_APP_PASSWORD.
  python -m notify.digest            (respects the once-a-day rule)
  python -m notify.digest --force    (send now)
"""
import csv
import html
import json
import os
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402

DATA_DIR = os.environ.get("DATA_DIR", "data")
IST = timezone(timedelta(hours=5, minutes=30))


def jload(path, default):
    try:
        with open(os.path.join(DATA_DIR, path)) as f:
            return json.load(f)
    except Exception:
        return default


def csv_rows(path):
    try:
        with open(os.path.join(DATA_DIR, path), newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def build(state, now=None):
    now = now or time.time()
    tracker = jload("tracker/tracker.json", {"items": {}, "earnings": []})
    st = lambda k, d="": tracker["items"].get(k, {}).get("status", d)
    since = state.get("digest_last_ts", now - 86400)
    gigs = [g for g in jload("gigs/gigs.json", {}).get("gigs", [])
            if g.get("visible") and st(f"gig:{g['id']}") not in ("hidden", "applied", "won", "lost")]
    fresh = sorted([g for g in gigs if (g.get("first_seen") or 0) > since], key=lambda g: -g.get("score", 0))
    top = (fresh or sorted(gigs, key=lambda g: -g.get("score", 0)))[:C.DIGEST_TOP_GIGS]
    cos = [r for r in csv_rows("jobs/outreach_plan.csv") if st(f"company:{r.get('company')}", "to contact") == "to contact"][:2]
    plat = next((p for p in sorted(C.AI_PLATFORMS, key=lambda p: p["priority"])
                 if p["priority"] < 9 and st(f"platform:{p['name']}", "not applied") == "not applied"), None)
    month = datetime.now(IST).strftime("%Y-%m")
    earned = sum(float(e.get("amount_inr", 0)) for e in tracker.get("earnings", []) if str(e.get("date", "")).startswith(month))
    return top, fresh, cos, plat, earned


def render(top, fresh, cos, plat, earned, space_url):
    e = html.escape
    lo, hi = C.MONTHLY_GOAL_INR
    gig_html = ""
    for g in top:
        pay = ""
        if g.get("pay_inr"):
            pay = f"~₹{g['pay_inr']:,.0f}{'/hr' if g.get('pay_type') == 'hourly' else ''}"
        ai = g.get("ai") or {}
        gig_html += f"""<tr><td style="padding:12px 0;border-bottom:1px solid #eceef3">
<div style="font-weight:600;font-size:15px"><a href="{e(g['url'])}" style="color:#2b4c9b;text-decoration:none">{e(g['title'])}</a></div>
<div style="color:#5b6170;font-size:13px;margin-top:3px">{e(g['source'])} · {e(pay)} · score {g.get('score')}</div>
<div style="font-size:14px;margin-top:6px;color:#2a2f3a">{e(ai.get('summary') or (g.get('desc') or '')[:180])}</div>
{('<div style="font-size:13px;margin-top:6px;color:#3d6b45">Draft ready in the app ✍️</div>' if ai.get('proposal') else '')}
</td></tr>"""
    if not gig_html:
        gig_html = "<tr><td style='padding:10px 0;color:#5b6170'>No new gigs since yesterday. The radar keeps checking every 6 hours.</td></tr>"
    co_html = "".join(
        f"<li style='margin-bottom:8px'><b>{e(r['company'])}</b> — {e(r.get('contact_1') or 'see app')} "
        f"({e(r.get('contact_1_role') or '')}) <span style='color:#5b6170'>{e(r.get('contact_1_email') or '')}</span><br>"
        f"<span style='color:#5b6170;font-size:13px'>💡 {e(r.get('talking_point') or '')}</span></li>" for r in cos)
    plat_html = (f"<p style='margin:0'>Apply to <a href='{e(plat['url'])}'>{e(plat['name'])}</a> "
                 f"({e(plat['fit'])}, {e(plat['pay'])}). It takes about 20 minutes.</p>") if plat else ""
    return f"""<div style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:620px;margin:auto;color:#22262f;background:#fbfbfd;padding:24px">
<h2 style="margin:0 0 4px 0">Good morning, {e(C.PROFILE['first_name'])} ☀️</h2>
<p style="margin:0 0 18px 0;color:#5b6170">{len(fresh)} new gigs since yesterday. Earned this month: ₹{earned:,.0f} (goal ₹{lo:,}–{hi:,}).</p>
<h3 style="margin:16px 0 4px 0">💸 Best gigs to bid on</h3><table style="width:100%;border-collapse:collapse">{gig_html}</table>
{('<h3 style="margin:22px 0 6px 0">🏢 Email one of these startups</h3><ul style="padding-left:18px;margin:0">' + co_html + '</ul>') if co_html else ''}
{('<h3 style="margin:22px 0 6px 0">🤖 This week</h3>' + plat_html) if plat_html else ''}
<p style="margin-top:24px"><a href="{e(space_url)}" style="background:#2b4c9b;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none">Open Career Hub</a></p>
<p style="color:#8a90a0;font-size:12px;margin-top:18px">Sent automatically by your Career Hub. Nothing to maintain.</p></div>"""


def send(html_body, subject):
    user, pw = os.environ.get("GMAIL_ADDRESS"), os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("DIGEST_TO") or user
    if not (user and pw):
        print("digest: GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set, skipped")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    print("digest: sent to", to)
    return True


def main(force=False):
    state = jload("gigs/state.json", {})
    now_ist = datetime.now(IST)
    today = now_ist.strftime("%Y-%m-%d")
    if not force and (now_ist.hour < C.DIGEST_HOUR_IST or state.get("digest_last_day") == today):
        print("digest: not due yet")
        return
    top, fresh, cos, plat, earned = build(state)
    space_url = os.environ.get("SPACE_URL")
    if not space_url and os.environ.get("HF_TOKEN"):
        try:
            from common.hfstore import username
            space_url = f"https://huggingface.co/spaces/{username()}/career-hub"
        except Exception:
            pass
    space_url = space_url or "https://huggingface.co/spaces"
    body = render(top, fresh, cos, plat, earned, space_url)
    subject = f"🎯 {len(fresh)} new gigs · {now_ist.strftime('%d %b')}" + (f" · top: {top[0]['title'][:45]}" if top else "")
    if send(body, subject):
        state["digest_last_day"], state["digest_last_ts"] = today, time.time()
        os.makedirs(os.path.join(DATA_DIR, "gigs"), exist_ok=True)
        with open(os.path.join(DATA_DIR, "gigs", "state.json"), "w") as f:
            json.dump(state, f, indent=1)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
