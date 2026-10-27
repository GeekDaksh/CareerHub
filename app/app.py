"""Career Hub — one private page for paid gigs, AI-task platforms and startup outreach.
Runs on a private Hugging Face Space. Data comes from the private dataset that GitHub Actions refreshes.
"""
import io
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

import config as C

st.set_page_config(page_title="Career Hub", page_icon="🎯", layout="wide")

HF_TOKEN = os.environ.get("HF_TOKEN")
DATA_REPO = os.environ.get("DATA_REPO")
LOCAL_DIR = os.environ.get("DATA_DIR", "data")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
IST = timezone(timedelta(hours=5, minutes=30))

# ------------------------------------------------------------------ look
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 1.6rem; max-width: 1180px; }
.card { border: 1px solid rgba(120,130,150,.25); border-radius: 12px; padding: 14px 16px; margin: 0 0 10px 0;
        background: rgba(127,140,170,.06); }
.card h4 { margin: 0 0 4px 0; font-size: 1.02rem; line-height: 1.35; }
.chip { display: inline-block; font-size: .75rem; padding: 2px 8px; border-radius: 999px; margin: 2px 4px 2px 0;
        background: rgba(110,130,180,.14); }
.score { float: right; font-weight: 700; font-size: .95rem; padding: 2px 10px; border-radius: 8px; }
.s-hi { background: #d5edd5; color: #1d5b2a; } .s-mid { background: #fff2cc; color: #6b5200; } .s-lo { background: #f3e1d6; color: #6b3417; }
.muted { opacity: .72; font-size: .86rem; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data access
def _hf():
    from huggingface_hub import HfApi
    return HfApi(token=HF_TOKEN)


def _read_bytes(path):
    if HF_TOKEN and DATA_REPO:
        from huggingface_hub import hf_hub_download
        try:
            p = hf_hub_download(DATA_REPO, path, repo_type="dataset", token=HF_TOKEN, force_download=True)
        except Exception:
            return None
        with open(p, "rb") as f:
            return f.read()
    p = os.path.join(LOCAL_DIR, path)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    return None


@st.cache_data(ttl=600, show_spinner=False)
def read_json(path, default=None):
    b = _read_bytes(path)
    try:
        return json.loads(b) if b else default
    except Exception:
        return default


@st.cache_data(ttl=600, show_spinner=False)
def read_csv(path):
    b = _read_bytes(path)
    try:
        return pd.read_csv(io.BytesIO(b)) if b else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def read_raw(path):
    return _read_bytes(path)


def load_tracker():
    if "tracker" not in st.session_state:
        b = _read_bytes("tracker/tracker.json")
        st.session_state.tracker = json.loads(b) if b else {"items": {}, "earnings": []}
    return st.session_state.tracker


def save_tracker():
    t = st.session_state.tracker
    data = json.dumps(t, ensure_ascii=False, indent=1).encode()
    if HF_TOKEN and DATA_REPO:
        try:
            _hf().upload_file(path_or_fileobj=data, path_in_repo="tracker/tracker.json", repo_id=DATA_REPO,
                              repo_type="dataset", commit_message="tracker update")
        except Exception as e:
            st.error(f"Could not save: {e}")
    else:
        os.makedirs(os.path.join(LOCAL_DIR, "tracker"), exist_ok=True)
        with open(os.path.join(LOCAL_DIR, "tracker", "tracker.json"), "wb") as f:
            f.write(data)


def status_of(key, default=""):
    return load_tracker()["items"].get(key, {}).get("status", default)


def set_status(key, status, note=None):
    t = load_tracker()
    item = t["items"].get(key, {})
    item.update({"status": status, "updated": datetime.now(IST).isoformat(timespec="minutes")})
    if note is not None:
        item["note"] = note
    t["items"][key] = item
    save_tracker()


def ago(ts):
    if not ts:
        return "—"
    h = max(0.0, (time.time() - float(ts)) / 3600)
    return f"{int(h * 60)} min ago" if h < 1 else f"{int(h)} h ago" if h < 48 else f"{int(h / 24)} days ago"


def md(v):
    """Streamlit reads $...$ as maths; escape dollars in text."""
    return str(v).replace("$", "\\$")


def rupees(v):
    return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else f"₹{v:,.0f}"


def clean(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


# ------------------------------------------------------------------ load
gig_data = read_json("gigs/gigs.json", {"gigs": [], "updated": None})
gigs = gig_data.get("gigs", [])
health = read_json("gigs/health.json", {})
gstate = read_json("gigs/state.json", {})
plan = read_csv("jobs/outreach_plan.csv")
contacts = read_csv("jobs/contacts.csv")
roles = read_csv("jobs/jobs.csv")
ranked = read_csv("jobs/ranked.csv")
jobs_status = read_json("jobs/run_status.json", {})
tracker = load_tracker()

# ------------------------------------------------------------------ header
c1, c2 = st.columns([3, 1])
c1.markdown(f"## 🎯 Career Hub · {C.PROFILE['first_name']}")
c1.markdown(f"<span class='muted'>Gigs updated {ago(gig_data.get('updated'))} · companies updated "
            f"{jobs_status.get('finished_ist', '—')}</span>", unsafe_allow_html=True)
c2.write("")
if c2.button("↻ Refresh data", use_container_width=True):
    st.cache_data.clear()
    st.session_state.pop("tracker", None)
    st.rerun()

tabs = st.tabs(["🏠 Today", "💸 Gigs", "🤖 AI-task platforms", "🏢 Companies", "📋 Tracker", "🧰 Toolkit", "⚙️ Status"])


def gig_card(g, key_prefix):
    sc = g.get("score", 0)
    cls = "s-hi" if sc >= 65 else "s-mid" if sc >= 45 else "s-lo"
    pay = ""
    if g.get("pay_inr"):
        pay = f"~₹{g['pay_inr']:,.0f}{'/hr' if g.get('pay_type') == 'hourly' else (' fixed' if g.get('pay_type') == 'fixed' else '/yr')}"
    chips = [C.GIG_CATEGORIES.get(g.get("category"), {}).get("label", g.get("category")), g.get("source"), pay,
             f"{int(g['bids'])} bids" if isinstance(g.get("bids"), (int, float)) else "", ago(g.get("posted")),
             g.get("work_type") if g.get("work_type") not in (None, "unknown") else "",
             "⚠ check location" if g.get("eligibility") == "check" else ""]
    chip_html = "".join(f"<span class='chip'>{c}</span>" for c in chips if c)
    ai = g.get("ai") or {}
    summary = ai.get("summary") or (g.get("desc") or "")[:220]
    st.markdown(f"""<div class='card'><span class='score {cls}'>{sc}</span>
<h4><a href="{g['url']}" target="_blank">{md(g['title'])}</a></h4>{chip_html}
<div class='muted' style='margin-top:6px'>{md(summary)}</div>
<div class='muted' style='margin-top:4px'>Why: {'; '.join(g.get('why') or [])}
{(' · est. ' + str(ai.get('est_hours')) + ' h') if ai.get('est_hours') else ''}
{(' · ⚠ ' + ', '.join(ai.get('red_flags'))) if ai.get('red_flags') else ''}</div></div>""", unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns([2, 1, 1, 1])
    with b1:
        if ai.get("proposal"):
            with st.expander("Proposal draft (edit 2 lines, then send)"):
                st.code(ai["proposal"], language=None, wrap_lines=True)
    key = f"gig:{g['id']}"
    cur = status_of(key)
    if b2.button("⭐ Save" if cur != "saved" else "⭐ Saved", key=f"{key_prefix}s{g['id']}", use_container_width=True):
        set_status(key, "saved"); st.rerun()
    if b3.button("✅ Applied" if cur != "applied" else "✅ Applied ✓", key=f"{key_prefix}a{g['id']}", use_container_width=True):
        set_status(key, "applied"); st.rerun()
    if b4.button("🙈 Hide", key=f"{key_prefix}h{g['id']}", use_container_width=True):
        set_status(key, "hidden"); st.rerun()


def open_gigs():
    return [g for g in gigs if g.get("visible") and status_of(f"gig:{g['id']}") not in ("hidden", "applied", "won", "lost")]


# ------------------------------------------------------------------ TODAY
with tabs[0]:
    now = time.time()
    new24 = [g for g in open_gigs() if now - (g.get("first_seen") or 0) < 86400]
    month = datetime.now(IST).strftime("%Y-%m")
    earned = sum(float(e.get("amount_inr", 0)) for e in tracker.get("earnings", []) if str(e.get("date", "")).startswith(month))
    week_ago = (datetime.now(IST) - timedelta(days=7)).isoformat()
    actions = sum(1 for v in tracker["items"].values()
                  if v.get("status") in ("applied", "contacted", "replied", "interview", "won")
                  and v.get("updated", "") >= week_ago)
    to_contact = plan[[status_of(f"company:{n}") in ("", "to contact") for n in plan.get("company", [])]] if len(plan) else plan
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("New gigs (24 h)", len(new24))
    k2.metric("Applications this week", actions)
    k3.metric("Companies to contact", len(to_contact))
    lo, hi = C.MONTHLY_GOAL_INR
    k4.metric("Earned this month", rupees(earned), f"goal ₹{lo:,}–{hi:,}", delta_color="off")
    st.progress(min(1.0, earned / lo) if lo else 0.0)

    st.markdown("#### Do these today (≈30 min)")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**1 · Bid on the best new gigs**")
        best = sorted(open_gigs(), key=lambda g: -g.get("score", 0))[:3]
        if not best:
            st.info("No gigs yet — the radar runs every 6 hours.")
        for g in best:
            gig_card(g, "t")
    with right:
        st.markdown("**2 · Email one startup**")
        for r in to_contact.head(2).to_dict("records"):
            st.markdown(f"<div class='card'><h4>{r['company']}</h4>"
                        f"<span class='chip'>{clean(r.get('tier'))}</span><span class='chip'>{clean(r.get('fields'))}</span>"
                        f"<div class='muted'>{clean(r.get('contact_1'))} · {clean(r.get('contact_1_role'))}<br>"
                        f"{clean(r.get('contact_1_email')) or 'LinkedIn: ' + clean(r.get('contact_1_linkedin'))} "
                        f"{('(' + clean(r.get('contact_1_grade')) + ')') if clean(r.get('contact_1_grade')) else ''}<br>"
                        f"💡 {clean(r.get('talking_point'))}</div></div>", unsafe_allow_html=True)
        if not len(to_contact):
            st.info("Company list appears after the weekly job-finder run.")
        st.markdown("**3 · AI-task platforms**")
        todo_p = [p for p in sorted(C.AI_PLATFORMS, key=lambda p: p["priority"])
                  if p["priority"] < 9 and status_of(f"platform:{p['name']}", "not applied") == "not applied"][:2]
        active = [p["name"] for p in C.AI_PLATFORMS if status_of(f"platform:{p['name']}") == "active"]
        if active:
            st.success("Active on: " + ", ".join(active) + " — check them for new tasks.")
        for p in todo_p:
            st.markdown(f"- Apply to **[{p['name']}]({p['url']})** — {md(p['fit'])} · {md(p['pay'])}")

# ------------------------------------------------------------------ GIGS
with tabs[1]:
    f1, f2, f3, f4 = st.columns([2, 2, 1, 1])
    cats = f1.multiselect("Type", list(C.GIG_CATEGORIES), default=list(C.GIG_CATEGORIES),
                          format_func=lambda c: C.GIG_CATEGORIES[c]["label"])
    srcs = sorted({g["source"] for g in gigs})
    pick = f2.multiselect("Sources", srcs, default=srcs)
    min_score = f3.slider("Min score", 0, 100, 40, 5)
    only_new = f4.toggle("New (48 h)", value=False)
    show_saved = st.toggle("Show only saved", value=False)
    pool = [g for g in open_gigs() if g.get("category") in cats and g["source"] in pick and g.get("score", 0) >= min_score]
    if only_new:
        pool = [g for g in pool if time.time() - (g.get("first_seen") or 0) < 172800]
    if show_saved:
        pool = [g for g in pool if status_of(f"gig:{g['id']}") == "saved"]
    pool.sort(key=lambda g: (-g.get("score", 0), -(g.get("posted") or 0)))
    n = st.number_input("Show", 10, 200, 30, 10)
    st.caption(f"{len(pool)} gigs match. Hidden automatically: not open to India, scam signs, under ₹{C.MIN_HOURLY_INR}/hr"
               + ("" if C.SHOW_FULL_TIME else ", full-time jobs") + ".")
    for g in pool[:int(n)]:
        gig_card(g, "g")

# ------------------------------------------------------------------ AI PLATFORMS
with tabs[2]:
    st.markdown("Paid AI-training and evaluation work: flexible hours, paid weekly. "
                "Apply to the top three, and keep going until you're active on two. "
                "<span class='muted'>Pay and eligibility as reported in public comparisons (Oct 2026). "
                "Check each site first. Never pay anything to join.</span>", unsafe_allow_html=True)
    opts = ["not applied", "applied", "test / onboarding", "active", "rejected"]
    for p in sorted(C.AI_PLATFORMS, key=lambda p: p["priority"]):
        cA, cB = st.columns([4, 1.3])
        cA.markdown(f"<div class='card'><h4><a href='{p['url']}' target='_blank'>{p['name']}</a></h4>"
                    f"<span class='chip'>India: {md(p['india'])}</span><span class='chip'>{md(p['pay'])}</span>"
                    f"<span class='chip'>{p['payout']}</span><div class='muted'>Best for you: {p['fit']}</div></div>",
                    unsafe_allow_html=True)
        cur = status_of(f"platform:{p['name']}", "not applied")
        new = cB.selectbox("Status", opts, index=opts.index(cur) if cur in opts else 0, key=f"pf{p['name']}",
                           label_visibility="collapsed", disabled=p["priority"] >= 9)
        if new != cur:
            set_status(f"platform:{p['name']}", new); st.rerun()

# ------------------------------------------------------------------ COMPANIES
with tabs[3]:
    if not len(plan):
        st.info("The job finder runs every Monday. The first company list appears after its first run.")
    else:
        g1, g2, g3 = st.columns(3)
        tiers = sorted(plan["tier"].dropna().unique())
        t_pick = g1.multiselect("Tier", tiers, default=tiers)
        fields = sorted({f.strip() for v in plan["fields"].dropna() for f in str(v).split(",")})
        f_pick = g2.multiselect("Field", fields, default=fields)
        st_pick = g3.selectbox("Status", ["all", "to contact", "contacted", "replied", "interview", "no reply"])
        view = plan[plan["tier"].isin(t_pick) & plan["fields"].fillna("").apply(
            lambda v: any(f.strip() in f_pick for f in str(v).split(",")))].copy()
        view["status"] = [status_of(f"company:{c}", "to contact") for c in view["company"]]
        if st_pick != "all":
            view = view[view["status"] == st_pick]
        show = ["rank", "status", "tier", "company", "fields", "fit_score", "contact_1", "contact_1_role",
                "contact_1_email", "contact_1_grade", "channel"]
        st.dataframe(view[[c for c in show if c in view.columns]], use_container_width=True, hide_index=True)
        pick = st.selectbox("Open a company", view["company"].tolist())
        if pick:
            r = plan[plan["company"] == pick].iloc[0].to_dict()
            a, b = st.columns([3, 2])
            with a:
                st.markdown(f"### {pick}")
                rk = ranked[ranked["company"] == pick] if len(ranked) else ranked
                if len(rk):
                    x = rk.iloc[0]
                    st.markdown(f"{clean(x.get('what_they_do'))}\n\n"
                                f"**Founded** {clean(x.get('founded')).replace('.0', '') or '—'} · **City** {clean(x.get('city')) or '—'} · "
                                f"**Stage** {clean(x.get('stage')) or '—'} · **Last round** {clean(x.get('last_round')) or '—'} "
                                f"{clean(x.get('last_round_date'))}\n\n**Products:** {clean(x.get('products')) or '—'}\n\n"
                                f"**Research:** {clean(x.get('research_and_discoveries')) or '—'}\n\n"
                                f"**Why it fits:** {clean(x.get('why_it_fits'))}")
                    if clean(x.get("website")):
                        st.markdown(f"[Website]({x['website']})")
                st.markdown(f"**Talking point:** {md(clean(r.get('talking_point')))}")
                if clean(r.get("linkedin_note")):
                    st.markdown("**LinkedIn note**")
                    st.code(r["linkedin_note"], language=None, wrap_lines=True)
                if clean(r.get("email_draft")):
                    st.markdown(f"**Email draft** — subject: {clean(r.get('email_subject'))}")
                    st.code(r["email_draft"], language=None, wrap_lines=True)
            with b:
                opts = ["to contact", "contacted", "replied", "interview", "no reply"]
                cur = status_of(f"company:{pick}", "to contact")
                new = st.selectbox("Status", opts, index=opts.index(cur) if cur in opts else 0, key=f"co{pick}")
                if new != cur:
                    set_status(f"company:{pick}", new); st.rerun()
                cc = contacts[contacts["company"].isin([pick, r.get("_key", pick)])] if len(contacts) else contacts
                for c in cc.to_dict("records")[:8]:
                    st.markdown(f"<div class='card'><b>{c['name']}</b> · {clean(c.get('role'))}<br>"
                                f"<span class='muted'>{clean(c.get('email')) or 'no email'} "
                                f"{('· ' + clean(c.get('email_grade'))) if clean(c.get('email_grade')) else ''}<br>"
                                f"{('<a href=' + chr(39) + c['linkedin'] + chr(39) + ' target=_blank>LinkedIn</a> · ') if clean(c.get('linkedin')) else ''}"
                                f"sure they work there: {clean(c.get('person_confidence'))}</span></div>",
                                unsafe_allow_html=True)
                cj = roles[(roles["company"] == r.get("_key", pick)) | (roles["company"] == pick)] if len(roles) else roles
                if len(cj):
                    st.markdown("**Open roles**")
                    for j in cj.head(6).to_dict("records"):
                        st.markdown(f"- [{j['title']}]({j['url']}) {('· ' + clean(j.get('location'))) if clean(j.get('location')) else ''}")
        xb = read_raw("jobs/job_finder_results.xlsx")
        if xb:
            st.download_button("⬇ Full Excel (all sheets)", xb, "job_finder_results.xlsx")

# ------------------------------------------------------------------ TRACKER
with tabs[4]:
    items = tracker["items"]
    rows = []
    gig_by_id = {f"gig:{g['id']}": g for g in gigs}
    for k, v in items.items():
        kind, _, name = k.partition(":")
        label = gig_by_id[k]["title"] if k in gig_by_id else name
        rows.append({"type": kind, "item": label, "status": v.get("status"), "updated": v.get("updated", "")})
    df = pd.DataFrame(rows)
    if len(df):
        df = df[df["status"].ne("hidden")].sort_values("updated", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        won_key = st.selectbox("Mark a gig as won / lost",
                               [""] + [k for k, v in items.items() if k.startswith("gig:") and v.get("status") in ("applied", "saved")],
                               format_func=lambda k: gig_by_id.get(k, {}).get("title", k) if k else "—")
        if won_key:
            w1, w2 = st.columns(2)
            if w1.button("🏆 Won"):
                set_status(won_key, "won"); st.rerun()
            if w2.button("Lost"):
                set_status(won_key, "lost"); st.rerun()
    else:
        st.info("Nothing tracked yet. Use Save / Applied on gigs and statuses on companies and platforms.")

    st.markdown("#### 💰 Earnings")
    with st.form("earn", clear_on_submit=True):
        e1, e2, e3, e4 = st.columns([1, 1, 2, 2])
        d = e1.date_input("Date", datetime.now(IST).date())
        amt = e2.number_input("Amount (₹)", 0, 10_000_000, 0, 500)
        src = e3.text_input("From (client / platform)")
        note = e4.text_input("Note")
        if st.form_submit_button("Add") and amt > 0:
            tracker["earnings"].append({"date": d.isoformat(), "amount_inr": amt, "source": src, "note": note})
            save_tracker(); st.rerun()
    if tracker["earnings"]:
        e = pd.DataFrame(tracker["earnings"])
        e["month"] = e["date"].str[:7]
        by_m = e.groupby("month")["amount_inr"].sum()
        st.bar_chart(by_m)
        st.dataframe(e.sort_values("date", ascending=False), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ TOOLKIT
with tabs[5]:
    P = C.PROFILE
    st.markdown(f"""
#### Your weekly routine (under {C.HOURS_PER_WEEK} hours)
| When | What | Time |
|---|---|---|
| Daily, from the morning email | Bid on 1–2 top gigs using the draft. Change two lines so it's clearly yours. | 10 min |
| Once a week | Apply to one AI-task platform until you're active on two. Email two startups from **Companies**. | 1 h |
| Weekend | Do the paid work (gigs or AI tasks) | 4–6 h |
| End of month | Log earnings in **Tracker**, and drop gig types that never reply | 10 min |

#### Profile text (Freelancer.com, Upwork, Contra)
**Headline:** {P['headline']}
""")
    overview = (f"I'm {P['first_name']}, {P['intro']}. I build practical AI tools in Python: LLM apps and chatbots "
                f"(LangGraph, RAG with FAISS), computer vision, data automation and optimisation. Recent work: "
                + "; ".join(p['short'] for p in P['projects'][:3]) +
                ". I keep scope small and clear, share progress early, and deliver clean, documented code.")
    st.code(overview, language=None, wrap_lines=True)
    st.markdown("""
#### Starting rates (suggested; raise them after 5 good reviews)
| Work | Start | After 5 reviews |
|---|---|---|
| Small Python, scraping or automation task | ₹2,000–₹6,000 fixed (or \\$10–15/hr) | \\$20–30/hr |
| LLM chatbot / RAG prototype | ₹8,000–₹25,000 fixed | \\$25–40/hr |
| Technical article (1,000–1,500 words) | ₹2,000–₹4,000 | ₹5,000+ |
| AI-task platforms | the platform's rate | higher tiers unlock with quality scores |

#### Proposal formula (the drafts follow it)
1. Their problem, in their own words. 2. One proof: a project or skill that matches. 3. Your first step. 4. One question.
Short beats long. Send within a few hours of posting, while the bid count is low.

#### Scam check (the radar already hides most of these)
Walk away if a job asks you to pay anything, moves you to Telegram or WhatsApp, promises a fixed daily income, asks for bank, OTP or ID details, or wants the whole job done as a free "test".

#### Getting paid
- **Platforms:** use their built-in payout (PayPal, Payoneer, Wise, Stripe or Deel, depending on the platform).
- **Direct clients abroad:** Wise or Payoneer. Send an invoice and keep each payment's FIRA/FIRC from your bank.
- **Tax:** freelance income is taxable in India. Keep every invoice. Professionals can use presumptive tax (Section 44ADA). Ask a CA before your first ITR with freelance income.
""")

# ------------------------------------------------------------------ STATUS
with tabs[6]:
    st.markdown("#### Gig sources")
    hrows = [{"source": k, "ok": "✅" if v.get("ok") else "❌", "gigs": v.get("count"), "checked": ago(v.get("at")),
              "note": v.get("error", "")} for k, v in health.items()]
    st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)
    runs = gstate.get("runs", [])
    if runs:
        rdf = pd.DataFrame(runs)
        rdf["time"] = pd.to_datetime(rdf["at"], unit="s").dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata").dt.strftime("%d %b %H:%M")
        st.markdown("#### Last gig runs")
        st.dataframe(rdf[["time", "total", "visible", "new"]].iloc[::-1], use_container_width=True, hide_index=True)
    st.markdown("#### Job finder")
    st.json(jobs_status or {"status": "not run yet"})
    if GITHUB_REPO:
        st.markdown(f"Runs and logs: [github.com/{GITHUB_REPO}/actions](https://github.com/{GITHUB_REPO}/actions)")
    st.caption("A failed source fixes itself on the next run if the site was only down. If one stays ❌ for days, "
               "the site changed; the rest keep working.")
