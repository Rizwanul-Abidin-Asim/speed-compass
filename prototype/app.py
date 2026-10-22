"""Speed Compass: working prototype for Amazon Transcend 2026, Case Study 1.

Run:  python -m streamlit run app.py   (or double-click "Start Speed Compass.bat")
All numbers come from model/speed_ladder.py, the same code behind the submitted documents.
"""
import html
import json
import os
import socket

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from compass import bridge, content, cutoff, memo, urgency
from compass.ai import Claude

st.set_page_config(page_title="Speed Compass", page_icon=":material/explore:", layout="wide",
                   initial_sidebar_state="expanded")

INK, INK2, MUTED, LINE, AXIS = "#0f172a", "#475569", "#94a3b8", "#e2e8f0", "#cbd5e1"
VIOLET, CORAL, GOOD, BAD = "#6d3fd1", "#e11d48", "#12823b", "#c2334d"
ZONE_COLORS = {"Dubai": "#2a78d6", "Abu Dhabi region": "#eb6834", "Sharjah city and Ajman": "#1baf7a",
               "Al Ain": "#eda100", "Outer emirates": "#e87ba4"}
ZONE_DEEP = {"Dubai": "#1d5fbf", "Abu Dhabi region": "#d4541f", "Sharjah city and Ajman": "#0f8a63",
             "Al Ain": "#b97d00", "Outer emirates": "#c2477a"}
ZONE_TINT = {"Dubai": "#eaf2fd", "Abu Dhabi region": "#fdeee7", "Sharjah city and Ajman": "#e6f6ef",
             "Al Ain": "#fdf4dc", "Outer emirates": "#fcebf2"}
LABEL = {"Dubai": "Dubai", "Abu Dhabi region": "Abu Dhabi region", "Sharjah city and Ajman": "Sharjah-Ajman",
         "Al Ain": "Al Ain", "Outer emirates": "Outer emirates"}
FONT = "IBM Plex Sans, IBM Plex Sans Arabic, Segoe UI, system-ui, sans-serif"
CLOCK = ('<svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.4" '
         'fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 4.4V8l2.6 1.6" fill="none" '
         'stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans+Arabic:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root { --ink:#0f172a; --ink2:#475569; --muted:#94a3b8; --line:#e2e8f0; --violet:#6d3fd1;
        --good:#12823b; --goodbg:#e3f6e8; --bad:#c2334d; --badbg:#fde8ec;
        --dusk:linear-gradient(115deg,#1b3b6f 0%,#6b4c9a 58%,#e07a3f 100%); }
html, body, .stApp, .stMarkdown, p, li, label, input, textarea, button, [data-testid="stWidgetLabel"] {
  font-family:'IBM Plex Sans','IBM Plex Sans Arabic','Segoe UI',system-ui,sans-serif; }
.block-container { padding-top:1.1rem; max-width:1420px; }
[data-testid="stAppDeployButton"] { display:none; }

/* ---------- masthead: UAE dusk, with a horizon made of the zones' order shares ---------- */
.sc-mast { border-radius:20px; padding:24px 30px 18px; margin-bottom:18px; color:#fff;
  background:linear-gradient(160deg,#0b2545 0%,#1b3b6f 40%,#6b4c9a 72%,#f08a4b 100%);
  box-shadow:0 12px 32px rgba(27,59,111,.28); }
.sc-mast-top { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; flex-wrap:wrap; }
.sc-eyebrow { font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:rgba(255,255,255,.78); }
.sc-title { font-family:'Barlow Condensed','Arial Narrow',sans-serif; font-weight:700; font-size:58px; line-height:1;
  margin:6px 0 8px; letter-spacing:.01em; }
.sc-tag { font-size:16px; color:rgba(255,255,255,.9); max-width:640px; line-height:1.5; }
.sc-chips { display:flex; flex-direction:column; gap:8px; align-items:flex-end; }
.sc-chip { display:inline-flex; align-items:center; gap:8px; background:rgba(255,255,255,.15);
  border:1px solid rgba(255,255,255,.28); color:#fff; padding:6px 13px; border-radius:999px; font-size:13px;
  white-space:nowrap; }
.sc-dot { width:9px; height:9px; border-radius:50%; display:inline-block; flex:none; }
.sc-horizon { margin-top:20px; }
.sc-stripe { display:flex; height:12px; border-radius:999px; overflow:hidden; box-shadow:0 0 0 2px rgba(255,255,255,.3); }
.sc-stripe span { display:block; height:100%; }
.sc-legend { display:flex; flex-wrap:wrap; gap:6px 20px; margin-top:9px; font-size:13px; color:rgba(255,255,255,.88); }
.sc-legend b { color:#fff; font-weight:600; }
.sc-legend .sc-dot { margin-right:6px; box-shadow:0 0 0 2px rgba(255,255,255,.35); }
@media (max-width:760px) { .sc-chips { align-items:flex-start; } .sc-title { font-size:44px; } }

/* ---------- tabs as pills ---------- */
[role="tablist"] { gap:8px !important; flex-wrap:wrap; border:none !important; box-shadow:none !important;
  padding-bottom:6px; }
[role="tablist"]::before, [role="tablist"]::after, [data-testid="stTab"]::before, [data-testid="stTab"]::after {
  display:none !important; }
[data-testid="stTab"] { background:#fff !important; border:1px solid #dfe5f1 !important; border-radius:999px !important;
  padding:8px 18px !important; height:auto !important; min-height:0 !important; margin:0 !important;
  transition:background .15s ease, box-shadow .15s ease; }
[data-testid="stTab"]:hover { border-color:#b7a6e8 !important; }
[data-testid="stTab"] p { font-weight:600 !important; font-size:14.5px !important; color:var(--ink2) !important;
  white-space:nowrap; margin:0 !important; }
[data-testid="stTab"][aria-selected="true"] { background:var(--dusk) !important; border-color:transparent !important;
  box-shadow:0 4px 14px rgba(107,76,154,.32); }
[data-testid="stTab"][aria-selected="true"] p, [data-testid="stTab"][aria-selected="true"] span { color:#fff !important; }

/* ---------- buttons ---------- */
.stButton > button[kind="primary"] { background:var(--dusk); border:none; color:#fff; font-weight:600;
  border-radius:10px; box-shadow:0 4px 14px rgba(107,76,154,.32); }
.stButton > button[kind="primary"]:hover { filter:brightness(1.08); color:#fff; }
.stButton > button[kind="secondary"] { border-radius:999px; border:1px solid #d7ddef; background:#fff; }
.stButton > button[kind="secondary"]:hover { border-color:var(--violet); color:var(--violet); }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background:linear-gradient(180deg,#eaf0fc 0%,#f3eefb 55%,#fdf1e8 100%); }
.sc-side-h { display:flex; align-items:center; gap:9px; font-weight:700; font-size:14.5px; color:var(--ink);
  margin:16px 0 2px; }
.sc-side-h .sc-dot { width:11px; height:11px; }
.sc-side-title { font-family:'Barlow Condensed','Arial Narrow',sans-serif; font-size:28px; font-weight:700;
  background:var(--dusk); -webkit-background-clip:text; background-clip:text; color:transparent; line-height:1.1; }
.sc-keybox { background:#fff; border:1px solid #e4dcf7; border-radius:12px; padding:10px 12px; font-size:12.5px;
  color:var(--ink2); line-height:1.5; }

/* ---------- section titles and cards ---------- */
.sc-h { font-family:'Barlow Condensed','Arial Narrow',sans-serif; font-size:26px; font-weight:700; color:var(--ink);
  margin:2px 0 2px; display:flex; align-items:center; gap:10px; }
.sc-h::before { content:""; width:6px; height:24px; border-radius:3px; background:var(--dusk); flex:none; }
.sc-sub { font-size:13.5px; color:var(--ink2); margin-bottom:8px; }
[class*="st-key-card_"] { background:#fff !important; border-radius:18px !important; border:1px solid #e6eaf3 !important;
  box-shadow:0 3px 14px rgba(15,23,42,.06); padding:6px 8px !important; }

/* ---------- alternatives as mini-cards ---------- */
.sc-alts { display:flex; flex-direction:column; gap:10px; margin-top:6px; }
.sc-alt { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 14px;
  border-radius:14px; border:1px solid #e6eaf3; background:#fff; }
.sc-alt.lead { background:linear-gradient(110deg,#f1ecfe,#fff4ec); border-color:#d9ccf7; }
.sc-alt .t { font-weight:700; font-size:14.5px; color:var(--ink); }
.sc-alt .m { font-size:12.5px; color:var(--ink2); margin-top:3px; }
.sc-alt .r { font-family:'Barlow Condensed','Arial Narrow',sans-serif; font-size:30px; font-weight:700; line-height:1.1;
  padding:3px 12px; border-radius:12px; white-space:nowrap; text-align:center; }
.sc-alt .r small { display:block; font-family:'IBM Plex Sans',sans-serif; font-size:10.5px; font-weight:600;
  letter-spacing:.04em; text-transform:uppercase; }
.sc-alt .r.ok { background:var(--goodbg); color:var(--good); } .sc-alt .r.no { background:var(--badbg); color:var(--bad); }

/* ---------- zone board ---------- */
.sc-board { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:14px; margin-bottom:4px; }
@media (max-width:1150px) { .sc-board { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:640px) { .sc-board { grid-template-columns:1fr; } }
.sc-zone { background:#fff; border-radius:16px; overflow:hidden; border:1px solid #e6eaf3;
  box-shadow:0 3px 14px rgba(15,23,42,.07); }
.sc-zone-h { background:var(--zd); color:#fff; padding:12px 15px 11px; }
.sc-zone-h .name { font-family:'Barlow Condensed','Arial Narrow',sans-serif; font-size:23px; font-weight:700;
  line-height:1.05; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sc-zone-h .share { font-size:12.5px; opacity:.9; margin-top:2px; }
.sc-zone-b { padding:4px 15px 13px; background:linear-gradient(180deg,var(--zt) 0,#fff 110px); }
.sc-pw { display:flex; flex-wrap:wrap; align-items:center; gap:3px 8px; margin:12px 0 9px; }
.sc-promise { display:inline-flex; align-items:center; gap:6px; padding:5px 13px 5px 9px; border-radius:999px;
  font-family:'Barlow Condensed','Arial Narrow',sans-serif; font-size:20px; font-weight:700; line-height:1.1; }
.sc-promise.today { background:linear-gradient(110deg,#10b981,#059669); color:#fff;
  box-shadow:0 3px 10px rgba(16,185,129,.35); }
.sc-promise.tomorrow { background:linear-gradient(110deg,#fcd34d,#f59e0b); color:#3b2a00;
  box-shadow:0 3px 10px rgba(245,158,11,.3); }
.sc-promise.none { background:#e2e8f0; color:#334155; }
.sc-pnote { font-size:11.5px; color:var(--ink2); white-space:nowrap; }
.sc-row { display:flex; justify-content:space-between; align-items:baseline; gap:8px; font-size:13px; padding:4px 0;
  border-top:1px solid #edf0f6; color:var(--ink2); }
.sc-row span:first-child { min-width:0; }
.sc-row span:last-child { color:var(--ink); white-space:nowrap; }
.sc-num { font-family:'IBM Plex Mono',Consolas,monospace; font-variant-numeric:tabular-nums; font-size:12.5px; }
.sc-src { font-size:11px; color:var(--muted); margin-top:3px; }
.sc-verdict { margin-top:9px; font-size:12.5px; font-weight:500; padding:6px 9px; border-radius:8px; line-height:1.35; }
.sc-verdict.pass { background:var(--goodbg); color:var(--good); }
.sc-verdict.fail { background:var(--badbg); color:var(--bad); }

/* ---------- KPI tiles ---------- */
.sc-kpis { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; margin:16px 0 14px; }
@media (max-width:900px) { .sc-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); } }
.sc-kpi { border-radius:16px; padding:12px 16px 14px; background:var(--kb); border:1px solid rgba(15,23,42,.05); }
.sc-kpi .lab { font-size:11.5px; font-weight:700; color:var(--kc); text-transform:uppercase; letter-spacing:.07em; }
.sc-kpi .val { font-family:'Barlow Condensed','Arial Narrow',sans-serif; font-size:31px; font-weight:700;
  color:var(--ink); line-height:1.15; margin-top:2px; white-space:nowrap; }
.sc-kpi .sub { font-size:12px; color:var(--ink2); }
.sc-kpi .sub.pass { color:var(--good); font-weight:600; } .sc-kpi .sub.fail { color:var(--bad); font-weight:600; }

/* ---------- tables and chips ---------- */
.sc-t { width:100%; border-collapse:collapse; font-size:13.5px; }
.sc-t th { text-align:left; font-weight:600; color:var(--ink2); font-size:12px; text-transform:uppercase;
  letter-spacing:.05em; padding:7px 8px; border-bottom:2px solid #e6eaf3; }
.sc-t td { padding:9px 8px; border-bottom:1px solid #eef1f6; vertical-align:middle; }
.sc-t td.n { text-align:right; font-family:'IBM Plex Mono',Consolas,monospace; font-size:12.5px; white-space:nowrap; }
.sc-t th.n { text-align:right; }
.sc-t tr.lead td { background:#f4f0fd; font-weight:600; }
.sc-c { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap; }
.sc-c.ok { background:var(--goodbg); color:var(--good); } .sc-c.no { background:var(--badbg); color:var(--bad); }
.sc-c.urgent { background:linear-gradient(110deg,#f43f5e,#f97316); color:#fff; }
.sc-c.planned { background:#e2e8f0; color:#334155; }
.sc-c.minutes { background:#efe9fd; color:#5b34c2; } .sc-c.hours { background:#e6f0fd; color:#1d5fbf; }
.sc-c.day { background:#e3f6ee; color:#0f7a57; }
.sc-c.lvl-none { background:#eef2f7; color:#475569; } .sc-c.lvl-partial { background:#fff3d6; color:#8a5a00; }
.sc-c.lvl-full { background:#fde8ec; color:#b4233f; }
.sc-scroll { max-height:390px; overflow-y:auto; border-radius:10px; }
.sc-engine { font-size:12px; color:var(--muted); margin-top:6px; }
.sc-bubble-h { display:inline-flex; align-items:center; gap:8px; font-size:12px; font-weight:700; color:#fff;
  background:var(--dusk); padding:4px 12px; border-radius:999px; margin-bottom:8px; letter-spacing:.04em; }
.sc-foot { margin-top:26px; padding:14px 18px; border-radius:14px; background:#fff; border:1px solid #e6eaf3;
  font-size:12px; color:var(--ink2); }
[dir="rtl"] { font-family:'IBM Plex Sans Arabic','Segoe UI',sans-serif; }
</style>
"""

ss = st.session_state


# ------------------------------------------------------------------ state
def _set_defaults():
    d = bridge.default_settings()
    ss.w_lost = d["lost_full"] * 100
    ss.w_lost_nd = d["lost_nd"] * 100
    ss.w_urgent = d["urgent_share"] * 100
    ss.w_aov = int(d["aov"])
    ss.w_lift = round(d["lift"] * 100, 2)
    ss.w_cost = d["cost_change"] * 100
    ss.w_rule = d["ratio_min"]
    ss.w_skew = d["skew"]
    ss.rivals = dict(d["rivals"])
    ss.measured = {}
    for z in bridge.ZONE_NAMES:
        ss[f"r_{z}"] = ss.rivals[z]


if "booted" not in ss:
    _set_defaults()
    ss.booted = True


def settings():
    return dict(lost_full=ss.w_lost / 100, lost_nd=ss.w_lost_nd / 100, aov=float(ss.w_aov),
                urgent_share=ss.w_urgent / 100, lift=ss.w_lift / 100, cost_change=ss.w_cost / 100,
                ratio_min=float(ss.w_rule), skew=float(ss.w_skew), rivals=dict(ss.rivals), measured=dict(ss.measured))


def reset_all():
    _set_defaults()
    for k in ("memo", "qa", "test"):
        ss.pop(k, None)


def clear_measured():
    ss.measured = {}


def sync_rivals():
    for z in bridge.ZONE_NAMES:
        if ss[f"r_{z}"] != ss.rivals[z]:
            ss.rivals[z] = ss[f"r_{z}"]
            ss.measured.pop(z, None)


def apply_event(change):
    for z, level in change.items():
        ss.rivals[z] = level
        ss[f"r_{z}"] = level
        ss.measured.pop(z, None)


def reset_rivals():
    d = bridge.default_settings()["rivals"]
    for z in bridge.ZONE_NAMES:
        ss.rivals[z] = d[z]
        ss[f"r_{z}"] = d[z]


def use_measured(zones):
    ss.measured = {z: round(v["measured"], 4) for z, v in zones.items()}


def use_urgent_share(value):
    ss.w_urgent = float(round(value * 100))


def set_text(key, value):
    ss[key] = value


@st.cache_data(show_spinner=False)
def cached_plan(key):
    return bridge.plan(json.loads(key))


@st.cache_data(show_spinner=False)
def cached_breakpoints(key, rates):
    return bridge.breakpoints(json.loads(key), list(rates))


@st.cache_data(show_spinner=False)
def cached_test(shares, rivals, world, days, seed):
    cells, zones, series = cutoff.run_test(dict(shares), dict(rivals), world, days, seed)
    return cells, zones, {f"{k[0]}|{k[1]}": v for k, v in series.items()}


def key_of(s):
    return json.dumps(s, sort_keys=True)


def usd(aed):
    return aed / bridge.AED_PER_USD / 1e6


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def esc(text):
    return html.escape(str(text))


def side_h(text, color):
    st.markdown(f'<div class="sc-side-h"><span class="sc-dot" style="background:{color}"></span>{text}</div>',
                unsafe_allow_html=True)


def section(title, sub=None):
    st.markdown(f'<div class="sc-h">{title}</div>' + (f'<div class="sc-sub">{sub}</div>' if sub else ""),
                unsafe_allow_html=True)


def card(name):
    return st.container(border=True, key=f"card_{name}")


SHARE = os.environ.get("SPEED_COMPASS_SHARE") == "1"
PUBLIC_URL = "https://speed-compass-uae.streamlit.app"


def lan_urls(port):
    """Addresses other devices on the same network can open (share mode only)."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is sent; this only picks the outgoing interface
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return [f"http://{ip}:{port}" for ip in sorted(ips) if not ip.startswith(("127.", "169.254."))]


def qr_data_uri(url):
    try:
        import segno
    except ImportError:
        return None
    return segno.make(url, error="m").svg_data_uri(scale=6, dark="#1b3b6f")


def base_layout(fig, height, **kw):
    fig.update_layout(height=height, plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(family=FONT, size=12, color=INK), **kw)
    return fig


# ------------------------------------------------------------------ sidebar
st.markdown(CSS, unsafe_allow_html=True)
with st.sidebar:
    if SHARE:
        urls = lan_urls(st.get_option("server.port"))
        side_h("Judges: try it on your phone", "#10b981")
        if urls:
            qr = qr_data_uri(urls[0])
            if qr:
                st.markdown(f'<div style="background:#fff;border-radius:14px;padding:10px;text-align:center;'
                            f'border:1px solid #e4dcf7"><img src="{qr}" alt="QR code for {urls[0]}" '
                            f'style="width:100%;max-width:200px"></div>', unsafe_allow_html=True)
            st.code(urls[0], language=None)
            for extra in urls[1:]:
                st.caption(f"Also: {extra}")
            st.caption("Join the same Wi-Fi or hotspot as this laptop, then scan. Each judge gets their own copy; "
                       "nothing they change affects anyone else.")
        else:
            st.warning("No network found. Connect this laptop to Wi-Fi or a phone hotspot, then restart.")
        st.divider()
    else:
        with st.expander("Open on your phone", icon=":material/qr_code_2:"):
            qr = qr_data_uri(PUBLIC_URL)
            if qr:
                st.markdown(f'<div style="background:#fff;border-radius:14px;padding:10px;text-align:center">'
                            f'<img src="{qr}" alt="QR code for {PUBLIC_URL}" style="width:100%;max-width:200px">'
                            f'</div>', unsafe_allow_html=True)
            st.code(PUBLIC_URL, language=None)
            st.caption("Each person who opens the link gets their own copy; nothing they change affects others.")
    st.markdown('<div class="sc-side-title">Assumptions</div>', unsafe_allow_html=True)
    st.caption("Defaults match the submitted document (Appendix A2). Move any slider and every number updates.")
    side_h("What speed is worth", "#10b981")
    st.slider("Urgent shoppers lost without same-day", 5.0, 40.0, step=1.0, key="w_lost", format="%.0f%%",
              help="Where a rival offers same-day or faster. Zones with a rival in some areas use 75% of this; "
                   "zones without a rival use 50%. The 12 PM test replaces this with measured rates.")
    st.slider("Urgent shoppers lost with a two-day promise", 2.0, 30.0, step=1.0, key="w_lost_nd", format="%.0f%%")
    st.slider("Urgent share of orders", 10.0, 35.0, step=1.0, key="w_urgent", format="%.0f%%")
    st.slider("Average order", 100, 400, step=10, key="w_aov", format="AED %d")
    st.slider("Sales lift per day saved", 0.2, 3.0, step=0.05, key="w_lift", format="%.2f%%",
              help="Published range 0.73% to 1.82%; the plan uses 1.45% (Fisher, Gallino and Xu, 2019).")
    side_h("What speed costs", "#f59e0b")
    st.slider("Delivery cost change", -30.0, 60.0, step=5.0, key="w_cost", format="%+.0f%%")
    side_h("Spending rule", VIOLET)
    st.slider("Extra sales needed per AED 1 spent", 3.0, 8.0, step=0.5, key="w_rule", format="%.1f",
              help="The case brief sets 5.")
    with st.expander("Advanced"):
        st.slider("Urgent orders already in today's same-day (x their share)", 1.0, 2.0, step=0.1, key="w_skew",
                  format="%.1fx", help="1.0 means today's same-day orders are a random mix of urgent and planned.")
    if ss.measured:
        st.success(f"Using 12 PM test results for {len(ss.measured)} zones.")
        st.button("Go back to assumed rates", on_click=clear_measured, width="stretch")
    st.button("Reset to document defaults", on_click=reset_all, width="stretch")
    st.divider()
    side_h("AI connection (optional)", "#e07a3f")
    st.selectbox("AI provider", ["gemini", "claude"], key="ai_provider",
                 format_func={"gemini": "Google Gemini (free tier)", "claude": "Anthropic Claude"}.get)
    st.text_input("API key", type="password", key="api_key",
                  help="Gemini keys start with AIza, Claude keys with sk-ant-. Kept only in this browser session.")
    st.markdown('<div class="sc-keybox"><b>What the key does.</b> It lets an AI model tag searches, write the memo '
                'and answer questions in English or Arabic. Without a key, built-in rules do the same jobs offline, '
                'so the demo always works.<br><br><b>Free Gemini key:</b> aistudio.google.com, then Get API key. '
                'Keep it private, like a password.</div>', unsafe_allow_html=True)


def _secrets_to_env():
    """On a hosted copy the key lives in Streamlit secrets; locally it can be an environment variable."""
    for name in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        if name in os.environ:
            continue
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
        if value:
            os.environ[name] = value


_secrets_to_env()
claude = Claude(ss.get("ai_provider", "gemini"), ss.get("api_key"))
S = settings()
R = cached_plan(key_of(S))
Z = {z["zone"]: z for z in R["zones"]}

# ------------------------------------------------------------------ masthead
_ai_name = "Gemini" if claude.provider == "gemini" else "Claude"
ai_chip = (f'<span class="sc-dot" style="background:#34d399"></span>AI: {_ai_name} connected' if claude.configured()
           else '<span class="sc-dot" style="background:#cbd5e1"></span>AI: offline rules')
stripe = "".join(f'<span style="width:{z["order_share"] * 100:.2f}%;background:{ZONE_COLORS[z["zone"]]}"></span>'
                 for z in R["zones"])
legend = "".join(f'<span><span class="sc-dot" style="background:{ZONE_COLORS[z["zone"]]}"></span>'
                 f'<b>{LABEL[z["zone"]]}</b> {pct(z["order_share"])}</span>' for z in R["zones"])
st.markdown(f"""
<div class="sc-mast">
  <div class="sc-mast-top">
    <div>
      <div class="sc-eyebrow">Amazon Transcend 2026 &nbsp;|&nbsp; Case Study 1 prototype</div>
      <div class="sc-title">Speed Compass</div>
      <div class="sc-tag">Sets each zone's delivery promise with one rule: a step of speed is funded only if it brings
      {S['ratio_min']:.1f} times its cost in extra sales.</div>
    </div>
    <div class="sc-chips">
      <span class="sc-chip">{CLOCK}&nbsp;Same-day cut-off 12:00</span>
      <span class="sc-chip"><span class="sc-dot" style="background:#fcd34d"></span>Illustrative data, not Amazon data</span>
      <span class="sc-chip">{ai_chip}</span>
    </div>
  </div>
  <div class="sc-horizon">
    <div class="sc-stripe">{stripe}</div>
    <div class="sc-legend">{legend}<span style="opacity:.75">share of UAE orders</span></div>
  </div>
</div>""", unsafe_allow_html=True)

tab_plan, tab_test, tab_tag, tab_rival, tab_memo = st.tabs(
    [":material/route: Plan", ":material/schedule: 12 PM test", ":material/bolt: Urgency tagger",
     ":material/radar: Rival watch", ":material/description: Memo and questions"])


# ------------------------------------------------------------------ plan tab
def zone_card(z):
    name = z["zone"]
    lost, src = bridge.lost_rate(S, name)
    raise_sd = z["sd1"] > z["sd0"] + 1e-9
    raise_nd = z["nd1"] > z["nd0"] + 1e-9
    if raise_sd:
        chip = (f'<div class="sc-pw"><span class="sc-promise today">{CLOCK} Today</span>'
                f'<span class="sc-pnote">for urgent orders</span></div>')
    elif raise_nd:
        chip = (f'<div class="sc-pw"><span class="sc-promise tomorrow">{CLOCK} Tomorrow</span>'
                f'<span class="sc-pnote">for urgent items</span></div>')
    else:
        chip = f'<div class="sc-pw"><span class="sc-promise none">{CLOCK} No change</span></div>'
    first, rule = z["sd_first_ratio"], S["ratio_min"]
    verdict = (f'<div class="sc-verdict pass">&#10003; First same-day step returns {first:.1f} per AED 1</div>'
               if first >= rule else
               f'<div class="sc-verdict fail">&#10007; First same-day step returns {first:.1f}, below {rule:.1f}</div>')
    sd = f"{pct(z['sd0'])} &rarr; {pct(z['sd1'])}" if raise_sd else f"{pct(z['sd0'])} (hold)"
    return f"""
<div class="sc-zone" style="--zd:{ZONE_DEEP[name]};--zt:{ZONE_TINT[name]}">
  <div class="sc-zone-h"><div class="name">{LABEL[name]}</div><div class="share">{pct(z['order_share'])} of UAE orders</div></div>
  <div class="sc-zone-b">
    {chip}
    <div class="sc-row"><span>Same day</span><span class="sc-num">{sd}</span></div>
    <div class="sc-row"><span>By next day</span><span class="sc-num">{pct(z['nd0'])} &rarr; {pct(z['nd1'])}</span></div>
    <div class="sc-row"><span>Spend</span><span class="sc-num">AED {z['cost'] / 1e6:.1f}M</span></div>
    <div class="sc-row"><span>Extra sales</span><span class="sc-num">AED {z['value'] / 1e6:.1f}M</span></div>
    <div class="sc-row"><span>Lost sales</span><span class="sc-num">{pct(lost, 1)}</span></div>
    <div class="sc-src">{'Lost-sale rate measured by the 12 PM test' if src == '12 PM test' else 'Lost-sale rate assumed'}</div>
    {verdict}
  </div>
</div>"""


def kpi(label, value, sub, bg, accent, sub_cls=""):
    return (f'<div class="sc-kpi" style="--kb:{bg};--kc:{accent}"><div class="lab">{label}</div>'
            f'<div class="val">{value}</div><div class="sub {sub_cls}">{sub}</div></div>')


def ladder_figure():
    curves = bridge.curves(S, "sd")
    rule = S["ratio_min"]
    ymax = max(9.5, max(z["sd_first_ratio"] for z in R["zones"]) * 1.1)
    fig = go.Figure()
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=rule, y1=ymax, fillcolor="#e9f9ef", line_width=0,
                  layer="below")
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=0, y1=rule, fillcolor="#fff0f2", line_width=0,
                  layer="below")
    fig.add_annotation(xref="paper", x=0.01, y=ymax * 0.97, text="<b>Pays</b>", showarrow=False, xanchor="left",
                       yanchor="top", font=dict(size=12, color=GOOD))
    fig.add_annotation(xref="paper", x=0.01, y=rule * 0.94, text="<b>Does not pay</b>", showarrow=False,
                       xanchor="left", yanchor="top", font=dict(size=12, color=BAD))
    for z in R["zones"]:
        name, color = z["zone"], ZONE_COLORS[z["zone"]]
        steps = curves[name]
        funded = [s for s in steps if s["to"] <= z["sd1"] + 1e-9] if z["sd1"] > z["sd0"] + 1e-9 else []
        rest = steps[len(funded):]

        def path(items):
            xs, ys = [], []
            for s in items:
                xs += [s["frm"] * 100, s["to"] * 100]
                ys += [s["ratio"], s["ratio"]]
            return xs, ys

        hover = f"<b>{LABEL[name]}</b><br>Same-day %{{x:.1f}}%<br>Next step returns %{{y:.2f}} per AED 1<extra></extra>"
        if funded:
            fx, fy = path(funded)
            fig.add_trace(go.Scatter(x=fx, y=fy, mode="lines", name=LABEL[name], legendgroup=name,
                                     line=dict(color=color, width=3.2), hovertemplate=hover))
            fig.add_trace(go.Scatter(x=[fx[-1]], y=[fy[-1]], mode="markers", showlegend=False, legendgroup=name,
                                     marker=dict(size=12, color=color, line=dict(color="white", width=2.5)),
                                     hovertemplate=f"<b>{LABEL[name]}</b> stops at %{{x:.1f}}% same-day<extra></extra>"))
        rx, ry = path(rest)
        if funded:
            rx, ry = [fx[-1]] + rx, [fy[-1]] + ry
        fig.add_trace(go.Scatter(x=rx, y=ry, mode="lines", legendgroup=name, opacity=0.45,
                                 name=LABEL[name] + ("" if not funded else " (not funded)"), showlegend=not funded,
                                 line=dict(color=color, width=2, dash="dot"), hovertemplate=hover))
    fig.add_hline(y=rule, line=dict(color=VIOLET, width=2))
    fig.add_annotation(x=59, y=rule, text=f"<b>{rule:.1f} to 1 rule</b>", showarrow=False, xanchor="right",
                       yanchor="bottom", font=dict(size=12, color=VIOLET))
    return base_layout(fig, 440, margin=dict(l=8, r=8, t=12, b=8), hovermode="closest",
                       legend=dict(orientation="h", yanchor="top", y=-0.17, x=0, font=dict(size=12)),
                       xaxis=dict(title="Same-day share of the zone's orders", ticksuffix="%", range=[0, 60],
                                  showgrid=False, showline=True, linecolor=AXIS, zeroline=False),
                       yaxis=dict(title="Sales per AED 1 (next step)", range=[0, ymax], gridcolor="rgba(15,23,42,.06)",
                                  zeroline=False))


def breakpoint_figure():
    rates = tuple(round(r, 3) for r in np.arange(0.05, 0.401, 0.025))
    bp = cached_breakpoints(key_of(S), rates)
    names = bridge.ZONE_NAMES
    zv = [[(b - a) * 100 for a, b in bp[n]] for n in names]
    tx = [[(f"{b * 100:.0f}%" if b > a + 1e-9 else "hold") for a, b in bp[n]] for n in names]
    xlab = [f"{r * 100:g}%" for r in rates]
    fig = go.Figure(go.Heatmap(
        z=zv, x=xlab, y=[LABEL[n] for n in names], text=tx, texttemplate="%{text}",
        textfont=dict(size=12, color=INK), colorscale=[[0, "#ffe4e8"], [0.001, "#d1f5e0"], [1, "#3fbf7f"]],
        showscale=False, xgap=3, ygap=3,
        hovertemplate="%{y}<br>Lost-sale rate %{x}<br>Same-day target %{text}<extra></extra>"))
    current = min(range(len(rates)), key=lambda i: abs(rates[i] - S["lost_full"]))
    fig.add_shape(type="rect", x0=current - 0.5, x1=current + 0.5, y0=-0.5, y1=len(names) - 0.5,
                  line=dict(color=VIOLET, width=3), fillcolor="rgba(0,0,0,0)")
    fig.add_annotation(x=current, y=-0.5, text=f"<b>Plan uses {S['lost_full'] * 100:.0f}%</b>", showarrow=False,
                       yanchor="bottom", yshift=2, font=dict(size=12, color=VIOLET))
    return base_layout(fig, 300, margin=dict(l=8, r=8, t=30, b=8),
                       xaxis=dict(title="Urgent shoppers lost without same-day (where a rival offers it)",
                                  type="category", showgrid=False),
                       yaxis=dict(autorange="reversed", showgrid=False))


with tab_plan:
    st.markdown('<div class="sc-board">' + "".join(zone_card(z) for z in R["zones"]) + "</div>",
                unsafe_allow_html=True)
    rule = S["ratio_min"]
    ratio = R["ratio_delivery"] or 0
    y27 = bridge.spend_2027(R)
    spend27 = usd(y27["spend"])
    envelope = ("inside the USD 6M to 10M envelope" if 6 <= spend27 <= 10 else
                "under the USD 6M to 10M envelope" if spend27 < 6 else "over the USD 10M envelope")
    passes = ratio >= rule
    st.markdown('<div class="sc-kpis">' +
                kpi("UAE same-day", f"{pct(R['sd0'])} &rarr; {pct(R['sd1'])}", "share of orders, by Dec 2027",
                    "#eaf2fd", "#1d5fbf") +
                kpi("Next-day or faster", f"{pct(R['nd0'])} &rarr; {pct(R['nd1'])}", "start is our estimate",
                    "#e6f6ef", "#0f8a63") +
                kpi("Spend in 2027", f"USD {spend27:.1f}M", f"envelope USD 6M to 10M<br>USD "
                                                             f"{usd(R['total_cost']):.1f}M a year from 2028",
                    "#fff4e0", "#b06c00") +
                kpi("Extra sales in 2027", f"USD {usd(y27['value']):.1f}M",
                    f"USD {usd(R['total_value']):.1f}M a year from 2028", "#f3ecff", "#6d3fd1") +
                kpi("Return per AED 1", f"{ratio:.1f}",
                    f"{'&#10003; clears' if passes else '&#10007; misses'} the {rule:.1f} to 1 rule<br>"
                    f"on delivery cost",
                    "#e3f6e8" if passes else "#fde8ec", GOOD if passes else BAD, "pass" if passes else "fail") +
                "</div>", unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="medium")
    with left:
        with card("ladder"):
            section("The ladder", "Each line is one zone. Funding climbs while the next step stays in the green, "
                                  "then stops where urgent orders run out.")
            st.plotly_chart(ladder_figure(), width="stretch", config={"displayModeBar": False})
    with right:
        with card("alts"):
            section("Against the alternatives", "Same assumptions, three ways to spend.")
            alt = bridge.alternatives(S, R)
            plans = [("Speed Ladder", alt["ladder"], True)]
            if "even" in alt:
                plans.append(("Same budget, spread evenly", alt["even"], False))
            plans.append((f"Match rivals everywhere ({pct(alt['match']['target'])} same-day)", alt["match"], False))
            body = "".join(
                f'<div class="sc-alt {"lead" if lead else ""}"><div><div class="t">{name}</div>'
                f'<div class="m">Costs USD {usd(a["cost"]):.1f}M a year, brings USD {usd(a["value"]):.1f}M</div></div>'
                f'<div class="r {"ok" if a["ratio"] >= rule else "no"}">'
                f'{"&#10003;" if a["ratio"] >= rule else "&#10007;"} {a["ratio"]:.2f}<small>per AED 1</small></div></div>'
                for name, a, lead in plans)
            st.markdown(f'<div class="sc-alts">{body}</div>', unsafe_allow_html=True)
            st.markdown('<div class="sc-sub" style="margin-top:14px">Spreading money evenly pays for speed on '
                        'orders nobody was in a hurry for. Matching rivals everywhere buys same-day where vans make '
                        'few stops.</div>', unsafe_allow_html=True)

    with card("heat"):
        section("What would change the plan", "Same-day target by zone as the share of urgent shoppers lost "
                                              "without same-day moves. Green means same-day pays; rose means hold. "
                                              "This is the number the 12 PM test measures.")
        st.plotly_chart(breakpoint_figure(), width="stretch", config={"displayModeBar": False})

    with st.expander("Zone details"):
        detail = pd.DataFrame([{
            "Zone": LABEL[z["zone"]],
            "Decision": bridge.decision(z),
            "First same-day step": z["sd_first_ratio"],
            "First next-day step": z["nd_first_ratio"],
            "Break-even lost-sale rate": z["breakeven_lost_first"] * 100,
            "Urgent orders same-day": z["urgent_sd_share"] * 100,
            "Same-day stops to graduate": (None if z["sd1"] > z["sd0"] + 1e-9 or z["grad_stops"] == float("inf")
                                           else z["grad_stops"]),
            "Same-day stops today (est.)": bridge.STOPS_SD_TODAY[z["zone"]],
        } for z in R["zones"]])
        st.dataframe(detail, hide_index=True, width="stretch",
                     column_config={"First same-day step": st.column_config.NumberColumn(format="%.2f"),
                                    "First next-day step": st.column_config.NumberColumn(format="%.2f"),
                                    "Break-even lost-sale rate": st.column_config.NumberColumn(format="%.1f%%"),
                                    "Urgent orders same-day": st.column_config.NumberColumn(format="%.0f%%"),
                                    "Same-day stops to graduate": st.column_config.NumberColumn(format="%.0f")})


# ------------------------------------------------------------------ 12 PM test tab
def test_figure(d, title):
    m = cutoff.MINUTES
    p = cutoff.series_for_plot(d)
    labels = [f"{11 + (60 + x) // 60}:{(60 + x) % 60:02d}" for x in m]
    fig = go.Figure()
    fig.add_vrect(x0=-cutoff.DONUT, x1=0, fillcolor="#fff3d6", line_width=0, layer="below")
    for key, color, name in (("control", "#eb6834", "Items whose promise does not change"),
                             ("sameday", "#2a78d6", "Same-day items: Today before 12:00, Tomorrow after")):
        fig.add_trace(go.Scatter(x=m, y=p[key]["rate"] * 100, mode="markers", name=name,
                                 marker=dict(size=6, color=color, opacity=0.55), customdata=labels,
                                 hovertemplate="%{customdata}<br>%{y:.2f}% bought<extra></extra>"))
        for fx, fy in (p[key]["left_fit"], p[key]["right_fit"]):
            fig.add_trace(go.Scatter(x=list(fx), y=np.array(fy) * 100, mode="lines", showlegend=False,
                                     line=dict(color=color, width=3), hoverinfo="skip"))
    fig.add_vline(x=0, line=dict(color=CORAL, width=2))
    fig.add_annotation(x=0, y=1.0, yref="paper", text="<b>12:00 Today becomes Tomorrow</b>", showarrow=False,
                       xanchor="left", xshift=5, font=dict(size=12, color=CORAL))
    fig.add_annotation(x=-cutoff.DONUT / 2, y=0.02, yref="paper", text="rush, left out", showarrow=False,
                       font=dict(size=11, color="#8a5a00"))
    return base_layout(fig, 380, title=dict(text=title, font=dict(size=14)), margin=dict(l=8, r=8, t=44, b=8),
                       legend=dict(orientation="h", yanchor="bottom", y=-0.32, x=0),
                       xaxis=dict(tickmode="array", tickvals=list(range(-60, 61, 15)),
                                  ticktext=["11:00", "11:15", "11:30", "11:45", "12:00", "12:15", "12:30", "12:45",
                                            "13:00"], showgrid=False, showline=True, linecolor=AXIS),
                       yaxis=dict(title="Share of page views that bought", ticksuffix="%",
                                  gridcolor="rgba(15,23,42,.06)"))


with tab_test:
    with card("test_intro"):
        section("The 12 PM cut-off test",
                'Every day at 12:00 the promise on a same-day item flips from "Today" to "Tomorrow". Shoppers just '
                'before and just after are alike, so the drop in buying at 12:00, net of the same moment for items '
                'whose promise does not change, shows how many sales "Today" wins. Buyers who come back within seven '
                'days are delayed, not lost, and are removed. This tab runs the test on simulated data with a planted '
                'answer.')
        c1, c2, c3 = st.columns([2.2, 1.2, 0.8])
        world = c1.radio("Simulated world", list(cutoff.WORLDS), horizontal=True, key="t_world")
        days = c2.slider("Days of order history", 5, 40, 20, key="t_days")
        seed = c3.number_input("Random seed", 1, 999, 7, key="t_seed")
        if st.button("Run the 12 PM test", type="primary"):
            shares = tuple((z["zone"], z["order_share"]) for z in R["zones"])
            rivals = tuple((n, S["rivals"][n]) for n in bridge.ZONE_NAMES)
            with st.spinner("Running the test on every zone and item group"):
                ss.test = dict(result=cached_test(shares, rivals, world, days, seed), world=world, days=days)
    if ss.get("test"):
        cells, zones, series = ss.test["result"]
        with card("test_result"):
            section("What the test measured", f'Urgent item groups, {ss.test["days"]} days of history, world: '
                                              f'<b>{ss.test["world"]}</b>.')
            rows = ""
            for n in bridge.ZONE_NAMES:
                v = zones[n]
                now, src = bridge.lost_rate(S, n)
                rows += (f'<tr><td><span class="sc-dot" style="background:{ZONE_COLORS[n]};margin-right:8px"></span>'
                         f'{LABEL[n]}</td><td class="n"><b>{v["measured"] * 100:.1f}%</b></td>'
                         f'<td class="n">{v["lo"] * 100:.1f}% to {v["hi"] * 100:.1f}%</td>'
                         f'<td class="n">{now * 100:.1f}%</td><td>{src}</td></tr>')
            st.markdown(f'<table class="sc-t"><tr><th>Zone</th><th class="n">Measured lost-sale rate</th>'
                        f'<th class="n">90% range</th><th class="n">Plan uses now</th><th>Source now</th></tr>'
                        f'{rows}</table>', unsafe_allow_html=True)
            st.write("")
            st.button("Use these results in the plan", type="primary", on_click=use_measured, args=(zones,))
        with card("test_chart"):
            g1, g2 = st.columns(2)
            pick_zone = g1.selectbox("Zone", bridge.ZONE_NAMES, format_func=LABEL.get, key="t_zone")
            pick_group = g2.selectbox("Item group", [g["name"] for g in cutoff.ITEM_GROUPS], key="t_group")
            cell = next(c for c in cells if c["zone"] == pick_zone and c["group"] == pick_group)
            st.plotly_chart(test_figure(series[f"{pick_zone}|{pick_group}"],
                                        f"{LABEL[pick_zone]}, {pick_group}: measured lost-sale rate "
                                        f"{cell['measured'] * 100:.1f}% (90% range {cell['lo'] * 100:.1f}% to "
                                        f"{cell['hi'] * 100:.1f}%)"),
                            width="stretch", config={"displayModeBar": False})
        with st.expander("Check the method against the planted answer"):
            st.caption("In real use the true rate is unknown. Here the simulation planted it, so you can see the test "
                       "recover it.")
            st.dataframe(pd.DataFrame([{
                "Zone": LABEL[c["zone"]], "Item group": c["group"], "Urgent": "Yes" if c["urgent"] else "No",
                "Planted": c["true"] * 100, "Measured": c["measured"] * 100,
                "90% range": f"{c['lo'] * 100:.1f}% to {c['hi'] * 100:.1f}%",
                "Came back within 7 days": c["came_back"] * 100} for c in cells]), hide_index=True, width="stretch",
                column_config={k: st.column_config.NumberColumn(format="%.1f%%")
                               for k in ("Planted", "Measured", "Came back within 7 days")})


# ------------------------------------------------------------------ urgency tab
def tag_card(r):
    rtl = ' dir="rtl"' if r["language"] in ("ar", "mixed") else ""
    label = "URGENT: needed today" if r["label"] == "urgent" else "PLANNED: can wait"
    return f"""
<div style="margin:6px 0 14px">
  <div style="font-size:19px; font-weight:600; margin-bottom:10px;"{rtl}>{esc(r['query'])}</div>
  <span class="sc-c {r['label']}" style="font-size:13px; padding:5px 13px">{label}</span>
  <div class="sc-row" style="margin-top:12px;"><span>Item group</span><span>{esc(r['item_group'])}</span></div>
  <div class="sc-row"><span>Confidence</span><span class="sc-num">{float(r['confidence']):.2f}</span></div>
  <div class="sc-row"><span>Reason</span><span style="white-space:normal; text-align:right">{esc(r['reason'])}</span></div>
  <div class="sc-engine">Tagged by: {esc(r['engine'])}</div>
</div>"""


def donut(share):
    fig = go.Figure(go.Pie(values=[share, 1 - share], labels=["Urgent", "Planned"], hole=0.68, sort=False,
                           marker=dict(colors=["#f43f5e", "#cbd5e1"], line=dict(color="white", width=3)),
                           textinfo="none", hovertemplate="%{label}: %{percent}<extra></extra>"))
    fig.add_annotation(text=f"<b>{share:.0%}</b><br><span style='font-size:12px'>urgent</span>", showarrow=False,
                       font=dict(size=26, color=INK))
    return base_layout(fig, 210, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)


with tab_tag:
    a, b = st.columns(2, gap="medium")
    with a:
        with card("tag_one"):
            section("Tag one search", "Speed Compass reads a search in English or Arabic and decides whether the "
                                      "shopper needs it today.")
            st.text_input("Search text", key="u_query", placeholder="laptop charger tonight")
            ex = st.columns(2)
            for i, q in enumerate(content.EXAMPLE_SEARCHES):
                ex[i % 2].button(q, key=f"ex_{q}", on_click=set_text, args=("u_query", q), width="stretch")
            if st.button("Tag this search", type="primary"):
                q = (ss.get("u_query") or "").strip()
                if q:
                    with st.spinner("Tagging"):
                        ss.u_result = urgency.tag(claude, q)
                else:
                    st.warning("Type a search first, or pick an example.")
            if ss.get("u_result"):
                r, note = ss.u_result
                if note:
                    st.info(note)
                st.markdown(tag_card(r), unsafe_allow_html=True)
    with b:
        with card("tag_batch"):
            section("Tag an hour of searches", "30 searches standing in for one hour in Dubai (illustrative). The "
                                               "urgent share decides how far the ladder can climb.")
            if st.button("Tag all 30 searches"):
                with st.spinner("Tagging 30 searches"):
                    ss.u_batch = urgency.tag_batch(claude, content.SAMPLE_SEARCHES)
            if ss.get("u_batch"):
                res, note = ss.u_batch
                if note:
                    st.info(note)
                share = sum(r["label"] == "urgent" for r in res) / len(res)
                d1, d2 = st.columns([1, 1.4])
                with d1:
                    st.plotly_chart(donut(share), width="stretch", config={"displayModeBar": False})
                with d2:
                    st.markdown(f'<div class="sc-sub" style="margin-top:28px">Urgent share of this hour: '
                                f'<b>{share:.0%}</b>. The plan uses {S["urgent_share"]:.0%}.<br>Tagged by: '
                                f'{esc(res[0]["engine"])}.</div>', unsafe_allow_html=True)
                    st.button(f"Use {share:.0%} as the urgent share", on_click=use_urgent_share, args=(share,))
                rows = "".join(
                    f'<tr><td{" dir=rtl" if r["language"] in ("ar", "mixed") else ""}>{esc(r["query"])}</td>'
                    f'<td><span class="sc-c {r["label"]}">{r["label"]}</span></td><td>{esc(r["item_group"])}</td>'
                    f'<td class="n">{float(r["confidence"]):.2f}</td></tr>' for r in res)
                st.markdown(f'<div class="sc-scroll"><table class="sc-t"><tr><th>Search</th><th>Tag</th>'
                            f'<th>Item group</th><th class="n">Confidence</th></tr>{rows}</table></div>',
                            unsafe_allow_html=True)


# ------------------------------------------------------------------ rival tab
with tab_rival:
    with card("rival_controls"):
        section("Rival watch", "A faster rival raises how many urgent shoppers we lose without same-day. Speed Compass "
                               "matches a rival only when the step still clears the rule.")
        st.markdown("**Where a rival offers same-day or faster**")
        cols = st.columns(5)
        for col, n in zip(cols, bridge.ZONE_NAMES):
            col.selectbox(LABEL[n], bridge.RIVAL_LEVELS, format_func=bridge.RIVAL_LABEL.get, key=f"r_{n}",
                          on_change=sync_rivals)
        st.markdown("**Try a rival move**")
        ev = st.columns(2)
        for i, (label, change) in enumerate(content.RIVAL_EVENTS):
            ev[i % 2].button(label, on_click=apply_event, args=(change,), width="stretch")
        ev[len(content.RIVAL_EVENTS) % 2].button("Reset rivals to today", on_click=reset_rivals, width="stretch")
    with card("rival_impact"):
        section("Does matching pay?", f"Extra sales per AED 1 on the first same-day step, against the "
                                      f"{S['ratio_min']:.1f} to 1 rule.")
        base = cached_plan(key_of({**S, "rivals": bridge.default_settings()["rivals"]}))
        rows = ""
        for n in bridge.ZONE_NAMES:
            z, zb = Z[n], bridge.zone_row(base, n)
            lost, _ = bridge.lost_rate(S, n)
            level = S["rivals"][n]
            match = z["sd1"] > z["sd0"] + 1e-9
            moved = abs(z["sd_first_ratio"] - zb["sd_first_ratio"]) > 1e-9
            rows += (f'<tr><td><span class="sc-dot" style="background:{ZONE_COLORS[n]};margin-right:8px"></span>'
                     f'{LABEL[n]}</td><td><span class="sc-c lvl-{level}">{bridge.RIVAL_LABEL[level]}</span></td>'
                     f'<td class="n">{lost * 100:.1f}%</td><td class="n">{zb["sd_first_ratio"]:.2f}</td>'
                     f'<td class="n">{"<b>" if moved else ""}{z["sd_first_ratio"]:.2f}{"</b>" if moved else ""}</td>'
                     f'<td><span class="sc-c {"ok" if match else "no"}">'
                     f'{"&#10003; Yes, it pays" if match else "&#10007; No, it does not pay"}</span></td></tr>')
        st.markdown(f'<table class="sc-t"><tr><th>Zone</th><th>Rival</th><th class="n">Lost-sale rate</th>'
                    f'<th class="n">Before the move</th><th class="n">After</th><th>Match the rival?</th></tr>'
                    f'{rows}</table>', unsafe_allow_html=True)
    with card("rival_promises"):
        section("What rivals promise today", "From Appendix F of the supporting document.")
        rows = "".join(f'<tr><td><b>{esc(s)}</b></td><td><span class="sc-c {kind}">{esc(badge)}</span></td>'
                       f'<td>{esc(promise)}</td><td>{esc(cov)}</td><td>{esc(src)}</td></tr>'
                       for s, badge, kind, promise, cov, src in content.RIVAL_PROMISES)
        st.markdown(f'<table class="sc-t"><tr><th>Service</th><th>Speed</th><th>Promise</th><th>Coverage</th>'
                    f'<th>Source</th></tr>{rows}</table>', unsafe_allow_html=True)


# ------------------------------------------------------------------ memo tab
with tab_memo:
    a, b = st.columns([1.1, 1], gap="medium")
    with a:
        with card("memo"):
            section("This month's memo", "Written from the current plan. Change any assumption and write it again.")
            if st.button("Write this month's memo", type="primary"):
                with st.spinner("Writing the memo"):
                    ss.memo = dict(out=memo.memo(claude, R, S), key=key_of(S))
            if ss.get("memo"):
                text, engine, note = ss.memo["out"]
                if note:
                    st.info(note)
                if ss.memo["key"] != key_of(S):
                    st.warning("The plan changed after this memo was written. Write it again to update it.")
                st.markdown('<span class="sc-bubble-h">MONTHLY MEMO</span>', unsafe_allow_html=True)
                st.markdown(text)
                st.markdown(f'<div class="sc-engine">Written by: {esc(engine)}</div>', unsafe_allow_html=True)
    with b:
        with card("ask"):
            section("Ask Speed Compass", "Ask a what-if question in English or Arabic. It reruns the plan and "
                                         "explains what moves.")
            st.text_input("Question", key="q_text", placeholder="What happens in Al Ain if fuel costs rise 20%?")
            for q in content.EXAMPLE_QUESTIONS:
                st.button(q, key=f"q_{q}", on_click=set_text, args=("q_text", q))
            if st.button("Ask", type="primary"):
                q = (ss.get("q_text") or "").strip()
                if q:
                    with st.spinner("Rerunning the plan"):
                        ss.qa = dict(q=q, out=memo.answer(claude, S, q))
                else:
                    st.warning("Type a question first, or pick an example.")
            if ss.get("qa"):
                out = ss.qa["out"]
                if out["note"]:
                    st.info(out["note"])
                st.markdown('<span class="sc-bubble-h">SPEED COMPASS ANSWERS</span>', unsafe_allow_html=True)
                st.markdown(f"**Q:** {ss.qa['q']}")
                if urgency.language(ss.qa["q"]) == "ar" and out["engine"] != "Offline rules":
                    st.markdown(f'<div dir="rtl">{esc(out["text"])}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(out["text"])
                st.markdown(f'<div class="sc-engine">Answered by: {esc(out["engine"])}</div>', unsafe_allow_html=True)
                if out["before"] and out["after"]:
                    with st.expander("Numbers behind this answer"):
                        st.dataframe(pd.DataFrame([{
                            "Zone": LABEL[zb["zone"]], "Same-day before": zb["sd1"] * 100,
                            "Same-day after": za["sd1"] * 100, "First step before": zb["sd_first_ratio"],
                            "First step after": za["sd_first_ratio"], "Decision after": bridge.decision(za)}
                            for zb, za in zip(out["before"]["zones"], out["after"]["zones"])]),
                            hide_index=True, width="stretch",
                            column_config={"Same-day before": st.column_config.NumberColumn(format="%.1f%%"),
                                           "Same-day after": st.column_config.NumberColumn(format="%.1f%%"),
                                           "First step before": st.column_config.NumberColumn(format="%.2f"),
                                           "First step after": st.column_config.NumberColumn(format="%.2f")})

st.markdown('<div class="sc-foot">Prototype for Amazon Transcend 2026, Case Study 1, by <b>Rizwanul Abidin Asim</b> '
            '(American University of Sharjah). Inputs are the illustrative figures in the Supporting Document, not '
            'Amazon data. Production would run the language model on Amazon Bedrock.</div>', unsafe_allow_html=True)
