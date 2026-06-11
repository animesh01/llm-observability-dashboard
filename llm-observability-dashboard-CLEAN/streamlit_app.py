"""Conversational AI Observability - a model-health dashboard for a customer-facing
agentic AI assistant.

Organized around five buckets - Quality, Safety, Performance, Cost, Drift - plus an
executive summary, per-domain health, failure analysis, and alerts. Includes export
to PDF and PPTX, and a copy-to-clipboard executive summary.

All data is fabricated for demonstration - see the Data Disclaimer in the README.
"""
from __future__ import annotations

import html
import json
import sqlite3
from datetime import date
from pathlib import Path

import streamlit as st

from scripts.report_builders import exec_summary_text, build_pdf, build_pptx

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "telemetry.db"

# ---- palette: Option C light system, SLATE / STEEL accent ----
INK = "#1a1f2e"
MUTED = "#6f7689"
SLATE = "#4f5bd5"
SLATE_DK = "#3f49b8"
STEEL = "#5b6479"
AMBER = "#dd9421"
RED = "#e8654f"
GREEN = "#22b892"
VIOLET = "#8a7ef0"
CARD = "#ffffff"
LINE = "#e7e7f1"
BG = "#eaeaf3"
MINT = "#eef0fb"

st.set_page_config(page_title="AI Observability - Model Health",
                   page_icon="dashboard", layout="wide")


def esc(s) -> str:
    return html.escape(str(s))


@st.cache_data
def load_data() -> dict:
    """Read everything the dashboard needs from the SQLite database via SQL.

    The dashboard is genuinely database-backed: daily metrics, domain health,
    failure modes, intent agreement, and alerts are all SELECTed from
    data/telemetry.db (built by scripts/build_database.py).
    """
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    daily = [dict(r) for r in cur.execute(
        "SELECT * FROM daily_metrics ORDER BY day").fetchall()]
    domains = [dict(r) for r in cur.execute(
        "SELECT * FROM domain_health ORDER BY domain").fetchall()]
    failure_modes = [{"mode": r["mode"], "share": r["share"]} for r in cur.execute(
        "SELECT mode, share FROM failure_modes ORDER BY share DESC").fetchall()]
    intent_matrix = [{"intent": r["intent"], "volume": r["volume"],
                      "agreement": r["agreement"]} for r in cur.execute(
        "SELECT intent, volume, agreement FROM intent_agreement").fetchall()]
    alerts = [{"severity": r["severity"], "metric": r["metric"], "bucket": r["bucket"],
               "detail": r["detail"], "domain": r["domain"]} for r in cur.execute(
        "SELECT severity, metric, bucket, detail, domain FROM alerts").fetchall()]
    meta_rows = {r["key"]: r["value"] for r in cur.execute("SELECT key, value FROM meta").fetchall()}

    # demonstrate a live rollup from RAW events (used in the pipeline tab)
    raw_rollup = [dict(r) for r in cur.execute("""
        SELECT domain,
               COUNT(*)                         AS convos,
               ROUND(AVG(intent_correct)*100,1) AS intent_acc,
               ROUND(AVG(resolved)*100,1)       AS resolved_pct,
               ROUND(AVG(hallucinated)*100,2)   AS halluc_pct,
               ROUND(AVG(latency_ms))           AS avg_latency
        FROM conversation_events
        GROUP BY domain
        ORDER BY intent_acc ASC
    """).fetchall()]
    n_events = cur.execute("SELECT COUNT(*) FROM conversation_events").fetchone()[0]
    con.close()

    return {
        "meta": {
            "note": meta_rows.get("note", ""),
            "window_days": int(meta_rows.get("window_days", 30)),
            "domains": json.loads(meta_rows.get("domains", "[]")),
            "model_release_day": int(meta_rows.get("model_release_day", 18)),
            "events_per_day": int(meta_rows.get("events_per_day", 60)),
            "n_events": n_events,
        },
        "daily": daily,
        "domains": domains,
        "failure_modes": failure_modes,
        "intent_matrix": intent_matrix,
        "alerts": alerts,
        "raw_rollup": raw_rollup,
    }


def inject_styles() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
        .stApp {{ background:
            radial-gradient(1200px 500px at 18% -8%, #f4f4fb 0%, rgba(244,244,251,0) 60%),
            linear-gradient(180deg, #eaeaf3 0%, #e2e2ee 100%); }}
        html, body, [class*="css"] {{ font-family:"DM Sans",sans-serif; color:{INK}; }}
        h1,h2,h3,h4 {{ font-family:"Manrope",sans-serif !important; letter-spacing:-0.025em; color:{INK} !important; }}
        .stCaption, [data-testid="stCaptionContainer"] {{ color:{MUTED} !important; }}
        .hero {{ position:relative; overflow:hidden; border-radius:24px; padding:32px 36px; margin-bottom:18px; color:#fff;
            background:linear-gradient(135deg,#3a44a8 0%,#4f5bd5 52%,#7b84ec 100%);
            box-shadow:0 2px 2px rgba(30,28,80,.10), 0 16px 32px -10px rgba(60,55,170,.4), 0 44px 70px -24px rgba(60,55,170,.42); }}
        .hero::before {{ content:""; position:absolute; inset:0 0 auto 0; height:1px; border-radius:24px 24px 0 0;
            background:linear-gradient(90deg,transparent,rgba(255,255,255,.5),transparent); }}
        .hero h1, .hero h1 * {{ color:#fff !important; -webkit-text-fill-color:#fff !important; font-size:2.05rem; margin:8px 0 8px; }}
        .hero p {{ color:#eceafb !important; font-size:1.0rem; line-height:1.5; max-width:74%; margin:0; }}
        .hero p b {{ color:#fff !important; }}
        .hero .pill {{ display:inline-block; padding:6px 14px; border-radius:999px;
            background:rgba(255,255,255,0.22); color:#fff !important; font-size:0.72rem; font-weight:700;
            letter-spacing:0.06em; text-transform:uppercase; box-shadow:inset 0 1px 0 rgba(255,255,255,.3); }}
        .hero-art {{ position:absolute; right:28px; top:22px; opacity:0.96; filter:drop-shadow(0 12px 18px rgba(30,28,80,.3)); }}
        .status-row {{ display:flex; gap:13px; margin-top:20px; flex-wrap:wrap; }}
        .status {{ background:rgba(255,255,255,0.15); border-radius:13px; padding:10px 16px; box-shadow:inset 0 1px 0 rgba(255,255,255,.18); }}
        .status .n {{ font-size:1.3rem; font-weight:800; font-family:Manrope; color:#fff; }}
        .status .l {{ font-size:0.7rem; text-transform:uppercase; letter-spacing:0.05em; opacity:0.9; color:#fff; }}
        .section-title {{ font-family:Manrope; font-weight:800; font-size:1.28rem; margin:12px 0 2px; letter-spacing:-0.015em; }}
        .section-copy {{ color:{MUTED}; font-size:0.96rem; margin-bottom:14px; max-width:820px; line-height:1.5; }}
        .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }}
        .kpi-grid.three {{ grid-template-columns:repeat(3,1fr); }}
        .kpi {{ position:relative; background:linear-gradient(180deg,#fff,#fafaff); border:1px solid {LINE};
            border-radius:18px; padding:17px 19px;
            box-shadow:0 1px 1px rgba(30,28,80,.04), 0 6px 12px -3px rgba(30,28,80,.10), 0 20px 34px -12px rgba(30,28,80,.16);
            transition:transform .3s cubic-bezier(.2,.7,.2,1), box-shadow .3s; }}
        .kpi::before {{ content:""; position:absolute; inset:0 0 auto 0; height:1px; border-radius:18px 18px 0 0;
            background:linear-gradient(90deg,transparent,rgba(255,255,255,.9),transparent); }}
        .kpi:hover {{ transform:translateY(-4px);
            box-shadow:0 2px 2px rgba(30,28,80,.05), 0 10px 18px -4px rgba(30,28,80,.16), 0 28px 46px -16px rgba(30,28,80,.24); }}
        .kpi .lbl {{ font-size:0.72rem; font-weight:700; color:{MUTED}; text-transform:uppercase; letter-spacing:0.04em; }}
        .kpi .val {{ font-family:Manrope; font-weight:800; font-size:1.7rem; line-height:1.05; margin:8px 0 4px; letter-spacing:-0.03em; }}
        .kpi .val .u {{ font-size:0.9rem; color:{MUTED}; font-weight:700; }}
        .kpi .delta {{ font-size:0.78rem; font-weight:700; }}
        .kpi .def {{ font-size:0.74rem; color:#9aa0b0; line-height:1.4; margin-top:3px; }}
        .up-good {{ color:{GREEN}; }} .up-bad {{ color:{RED}; }} .flat {{ color:{MUTED}; }}
        .panel {{ position:relative; background:linear-gradient(180deg,#fff,#fafaff); border:1px solid {LINE};
            border-radius:20px; padding:22px 24px; margin-top:14px;
            box-shadow:0 1px 1px rgba(30,28,80,.04), 0 6px 12px -3px rgba(30,28,80,.10), 0 20px 34px -12px rgba(30,28,80,.16); }}
        .panel::before {{ content:""; position:absolute; inset:0 0 auto 0; height:1px; border-radius:20px 20px 0 0;
            background:linear-gradient(90deg,transparent,rgba(255,255,255,.9),transparent); }}
        .bucket-verdict {{ display:flex; align-items:center; gap:12px; margin:6px 0 14px; }}
        .bucket-verdict .chip {{ font-weight:800; font-size:0.8rem; padding:5px 13px; border-radius:10px; box-shadow:inset 0 1px 0 #fff; }}
        .bucket-verdict .txt {{ color:{MUTED}; font-size:0.95rem; }}
        .takeaway {{ background:linear-gradient(180deg,#fff,#fafaff); border:1px solid {LINE};
            border-left:3px solid {SLATE}; border-radius:14px; padding:14px 18px; font-size:0.95rem;
            line-height:1.5; margin:12px 0 4px; color:#565d6c;
            box-shadow:0 1px 1px rgba(30,28,80,.04), 0 6px 12px -3px rgba(30,28,80,.10); }}
        .takeaway b {{ font-family:Manrope; color:{INK}; }}
        .exec-card {{ position:relative; overflow:hidden; background:linear-gradient(180deg,#fff,#fafaff); border:1px solid {LINE};
            border-radius:22px; padding:24px 28px; margin-bottom:6px;
            box-shadow:0 2px 2px rgba(30,28,80,.05), 0 14px 28px -8px rgba(30,28,80,.18), 0 40px 64px -22px rgba(30,28,80,.28); }}
        .exec-card::before {{ content:""; position:absolute; inset:0 0 auto 0; height:3px; background:{SLATE}; border-radius:22px 22px 0 0; }}
        .exec-card h2 {{ font-size:1.3rem; margin:0 0 4px; }}
        .exec-card .lead {{ font-size:1.02rem; line-height:1.55; color:#454b5c; margin:6px 0 14px; }}
        .exec-card ul {{ margin:6px 0 0; padding-left:20px; }}
        .exec-card li {{ margin:5px 0; line-height:1.5; color:#565d6c; }}
        .alert {{ display:flex; gap:14px; align-items:flex-start; border-radius:14px; padding:15px 18px; margin-bottom:10px;
            border:1px solid {LINE}; background:#fff; box-shadow:0 6px 14px -10px rgba(30,28,80,.3); }}
        .alert .dot {{ width:12px; height:12px; border-radius:50%; margin-top:5px; flex-shrink:0; }}
        .alert.critical {{ border-left:4px solid {RED}; }} .alert.critical .dot {{ background:{RED}; }}
        .alert.warning {{ border-left:4px solid {AMBER}; }} .alert.warning .dot {{ background:{AMBER}; }}
        .alert.info {{ border-left:4px solid {SLATE}; }} .alert.info .dot {{ background:{SLATE}; }}
        .alert .body {{ flex:1; }}
        .alert .head {{ font-weight:800; font-family:Manrope; font-size:0.98rem; }}
        .alert .sev {{ font-size:0.66rem; font-weight:800; text-transform:uppercase; letter-spacing:0.05em; padding:2px 9px; border-radius:7px; margin-left:8px; }}
        .alert.critical .sev {{ background:#fbe9e6; color:#c1422c; }}
        .alert.warning .sev {{ background:#fbf1dc; color:#9a6a14; }}
        .alert.info .sev {{ background:{MINT}; color:{SLATE_DK}; }}
        .alert .detail {{ color:{MUTED}; font-size:0.88rem; margin-top:3px; line-height:1.45; }}
        .alert .where {{ color:{STEEL}; font-size:0.78rem; margin-top:4px; font-weight:600; }}
        table.tbl {{ width:100%; border-collapse:collapse; font-size:0.88rem; }}
        table.tbl th {{ text-align:left; padding:9px 11px; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.03em; color:{MUTED}; border-bottom:1px solid {LINE}; background:{MINT}; }}
        table.tbl td {{ padding:9px 11px; border-bottom:1px solid {LINE}; color:{INK}; }}
        .hbar {{ height:8px; border-radius:99px; background:#eceaf6; overflow:hidden; min-width:60px; }}
        .hbar > span {{ display:block; height:100%; border-radius:99px; }}
        .badge {{ display:inline-block; padding:2px 9px; border-radius:7px; font-weight:700; font-size:0.8rem; box-shadow:inset 0 1px 0 #fff; }}
        .stTabs [data-baseweb="tab-list"] {{ gap:9px; border-bottom:none !important; padding:4px 0 6px; flex-wrap:wrap; }}
        .stTabs [data-baseweb="tab"] {{ background:#fff !important; color:{MUTED} !important; border:1px solid {LINE} !important;
            border-radius:999px !important; padding:8px 16px !important; height:auto !important;
            box-shadow:0 4px 10px -6px rgba(30,28,80,.25), inset 0 1px 0 #fff !important;
            transition:transform .25s cubic-bezier(.2,.7,.2,1), box-shadow .25s, background .25s !important; }}
        .stTabs [data-baseweb="tab"] * {{ color:{MUTED} !important; }}
        .stTabs [data-baseweb="tab"]:hover {{ transform:translateY(-2px) !important; box-shadow:0 8px 16px -8px rgba(30,28,80,.3) !important; }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] {{ background:{MINT} !important; border-color:#d6d4f3 !important; transform:translateY(-3px) !important;
            box-shadow:0 10px 20px -8px rgba(79,91,213,.4), inset 0 1px 0 #fff !important; }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] * {{ color:{SLATE_DK} !important; font-weight:700 !important; }}
        .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none !important; background:transparent !important; }}
        [data-testid="stExpander"] {{ border:1px solid {LINE} !important; border-radius:14px; background:#fff; box-shadow:0 6px 14px -10px rgba(30,28,80,.3); overflow:hidden; }}
        [data-testid="stExpander"] details > summary, [data-testid="stExpander"] summary {{ background:{MINT} !important; border-bottom:1px solid #e2e0f6 !important; }}
        [data-testid="stExpander"] summary, [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] [class*="Header"], [data-testid="stExpander"] [class*="Header"] * {{ color:{INK} !important; -webkit-text-fill-color:{INK} !important; font-weight:700 !important; }}
        [data-testid="stExpander"] summary:hover * {{ color:{SLATE_DK} !important; -webkit-text-fill-color:{SLATE_DK} !important; }}
        [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{ background:#fff !important; }}
        [data-testid="stExpander"] p, [data-testid="stExpander"] li {{ color:{INK} !important; -webkit-text-fill-color:{INK} !important; }}
        .stButton button {{ border-radius:12px !important; font-weight:700 !important; border:1px solid {LINE} !important;
            background:#fff !important; color:{SLATE_DK} !important; box-shadow:0 4px 12px -6px rgba(30,28,80,.3) !important; }}
        .stButton button:hover {{ transform:translateY(-1px); border-color:#d6d4f3 !important; }}
        .stDownloadButton button {{ border-radius:12px !important; font-weight:700 !important; border:none !important;
            background:linear-gradient(180deg,{SLATE},{SLATE_DK}) !important; color:#fff !important;
            box-shadow:0 8px 18px -6px rgba(79,91,213,.5), inset 0 1px 0 rgba(255,255,255,.2) !important; }}
        .stDownloadButton button:hover {{ filter:brightness(1.07); transform:translateY(-1px); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- charts
def svg_sparkline(values, color=SLATE, height=80, fmt="{:.0%}", band=None, mark_incident=None, mark_release=None):
    W, H = 560, height
    pad_l, pad_r, pad_t, pad_b = 8, 46, 14, 16
    n = len(values)
    pw, ph = W - pad_l - pad_r, H - pad_t - pad_b
    vmin, vmax = min(values), max(values)
    span = (vmax - vmin) or 1
    vmin -= span * 0.2
    vmax += span * 0.2
    span = vmax - vmin
    X = lambda i: pad_l + (i / (n - 1)) * pw if n > 1 else pad_l
    Y = lambda v: pad_t + ph - ((v - vmin) / span) * ph
    out = f"<svg viewBox='0 0 {W} {H}' width='100%' style='display:block'>"
    if band is not None:
        by = Y(band)
        out += f"<line x1='{pad_l}' y1='{by:.1f}' x2='{pad_l+pw}' y2='{by:.1f}' stroke='{AMBER}' stroke-width='1.2' stroke-dasharray='4 4' opacity='0.7'/>"
    if mark_release is not None:
        rx = X(mark_release)
        out += f"<line x1='{rx:.1f}' y1='{pad_t}' x2='{rx:.1f}' y2='{pad_t+ph}' stroke='{VIOLET}' stroke-width='1.4' stroke-dasharray='2 3' opacity='0.7'/>"
        out += f"<text x='{rx+3:.1f}' y='{pad_t+9:.1f}' font-size='9' fill='{VIOLET}'>v-release</text>"
    if mark_incident is not None:
        ix = X(mark_incident)
        out += f"<line x1='{ix:.1f}' y1='{pad_t}' x2='{ix:.1f}' y2='{pad_t+ph}' stroke='{RED}' stroke-width='1' stroke-dasharray='3 3' opacity='0.4'/>"
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(values))
    out += f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/>"
    lx, lv = X(n - 1), values[-1]
    out += f"<circle cx='{lx:.1f}' cy='{Y(lv):.1f}' r='4' fill='{color}'/>"
    out += f"<text x='{lx+6:.1f}' y='{Y(lv)+4:.1f}' font-family='Manrope' font-weight='800' font-size='12' fill='{color}'>{fmt.format(lv)}</text>"
    out += "</svg>"
    return out


def svg_hbars(items, fmt="{:.0%}", maxv=None):
    maxv = maxv or max(v for _, v, _ in items) * 1.1
    out = "<div style='display:flex;flex-direction:column;gap:9px'>"
    for label, v, color in items:
        pct = max(2, (v / maxv) * 100)
        out += (f"<div style='display:flex;align-items:center;gap:12px'>"
                f"<div style='min-width:230px;font-size:0.9rem'>{esc(label)}</div>"
                f"<div class='hbar' style='flex:1'><span style='width:{pct:.0f}%;background:{color}'></span></div>"
                f"<div style='min-width:56px;text-align:right;font-weight:800;font-family:Manrope;font-size:0.9rem'>{fmt.format(v)}</div></div>")
    out += "</div>"
    return out


def kpi_color(val, good_high, warn, bad):
    if good_high:
        return GREEN if val >= warn else (AMBER if val >= bad else RED)
    return GREEN if val <= warn else (AMBER if val <= bad else RED)


# ---------------------------------------------------------------- app
inject_styles()
data = load_data()
daily = data["daily"]
domains = data["domains"]
latest = daily[-1]
prev = daily[-2]
first = daily[0]
release_day = data["meta"]["model_release_day"]


def delta_html(cur, old, invert=False, pct=True, suffix=""):
    diff = cur - old
    better = (diff < 0) if invert else (diff > 0)
    cls = "up-good" if (better and diff != 0) else ("up-bad" if diff != 0 else "flat")
    arrow = "\u25b2" if diff > 0 else ("\u25bc" if diff < 0 else "\u25aa")
    val = f"{abs(diff)*100:.1f} pts" if pct else f"{abs(diff):,.0f}{suffix}"
    return f"<span class='delta {cls}'>{arrow} {val} vs yesterday</span>"


def tile(label, value, unit, delta, definition):
    return (f"<div class='kpi'><div class='lbl'>{esc(label)}</div>"
            f"<div class='val'>{value}<span class='u'>{unit}</span></div>{delta}"
            f"<div class='def'>{esc(definition)}</div></div>")


def grid(tiles, three=False):
    cls = "kpi-grid three" if three else "kpi-grid"
    return f"<div class='{cls}'>{''.join(tiles)}</div>"


# ---- build the executive-summary summary dict (also feeds exports) ----
def verdict_for(name, ok):
    return ("Healthy", GREEN, "#e1f5ee", "#0f7d62") if ok else \
           ("Watch", AMBER, "#fbf1dc", "#9a6a14")


halluc_peak = max(d["hallucination_rate"] for d in daily)
intent_change = latest["intent_accuracy"] - first["intent_accuracy"]
drift_change = latest["intent_drift"] - first["intent_drift"]

status = "Needs attention" if (halluc_peak > 0.04 or latest["intent_drift"] > 0.15) else "Healthy"

buckets_summary = [
    {"name": "Quality", "ok": latest["resolution_rate"] >= 0.7 and latest["intent_accuracy"] >= 0.93,
     "verdict": f"Intent accuracy {latest['intent_accuracy']*100:.1f}%, resolution {latest['resolution_rate']*100:.0f}%, CSAT {latest['csat']:.2f}/5 - solid, but accuracy drifted down {abs(intent_change)*100:.1f} pts over the window.",
     "metrics": [("Intent accuracy", f"{latest['intent_accuracy']*100:.1f}%"),
                 ("Resolution rate", f"{latest['resolution_rate']*100:.0f}%"),
                 ("First-contact resolution", f"{latest['first_contact_resolution']*100:.0f}%"),
                 ("Repeat-contact rate", f"{latest['repeat_contact_rate']*100:.1f}%"),
                 ("CSAT", f"{latest['csat']:.2f}/5")]},
    {"name": "Safety", "ok": halluc_peak <= 0.04,
     "verdict": f"Groundedness {latest['groundedness_rate']*100:.0f}%, but hallucination risk spiked to {halluc_peak*100:.1f}% mid-window before recovering. {latest['jailbreak_attempts']} jailbreak attempts blocked today.",
     "metrics": [("Hallucination risk", f"{latest['hallucination_rate']*100:.1f}%"),
                 ("Groundedness", f"{latest['groundedness_rate']*100:.0f}%"),
                 ("Policy-violation rate", f"{latest['policy_violation_rate']*100:.2f}%"),
                 ("PII flags (today)", f"{latest['pii_flags']}"),
                 ("Jailbreak attempts (today)", f"{latest['jailbreak_attempts']}")]},
    {"name": "Performance", "ok": latest["p95_latency_ms"] < 3000,
     "verdict": f"Median latency {latest['latency_ms']:,} ms, p95 {latest['p95_latency_ms']:,} ms, uptime {latest['uptime']*100:.2f}%. The incident briefly breached the 3s p95 SLA.",
     "metrics": [("Median latency", f"{latest['latency_ms']:,} ms"),
                 ("Time-to-first-token", f"{latest['ttft_ms']:,} ms"),
                 ("p95 latency", f"{latest['p95_latency_ms']:,} ms"),
                 ("Tool-call failure", f"{latest['tool_failure_rate']*100:.1f}%"),
                 ("Uptime", f"{latest['uptime']*100:.2f}%")]},
    {"name": "Cost", "ok": True,
     "verdict": f"${latest['cost_per_convo']:.4f} per conversation, ${latest['cost_per_resolved']:.4f} per resolved. Cache-hit {latest['cache_hit_rate']*100:.0f}% improved after the new model shipped.",
     "metrics": [("Cost / conversation", f"${latest['cost_per_convo']:.4f}"),
                 ("Cost / resolved", f"${latest['cost_per_resolved']:.4f}"),
                 ("Tokens / conversation", f"{latest['tokens_per_convo']:,}"),
                 ("Cache-hit rate", f"{latest['cache_hit_rate']*100:.0f}%")]},
    {"name": "Drift", "ok": latest["intent_drift"] <= 0.15,
     "verdict": f"Intent drift rose {drift_change*100:.0f} pts to {latest['intent_drift']*100:.0f}% over 30 days - the clearest early-warning signal. A new model shipped day {release_day}.",
     "metrics": [("Intent drift", f"{latest['intent_drift']*100:.0f}%"),
                 ("Topic drift", f"{latest['topic_drift']*100:.0f}%"),
                 ("Quality drift", f"{latest['quality_drift']*100:.0f}%"),
                 ("Model release", f"day {release_day}")]},
]

summary = {
    "window_days": data["meta"]["window_days"],
    "status": status,
    "headline": (f"The assistant is largely {('healthy' if status=='Healthy' else 'stable but needs attention')}: "
                 f"intent accuracy is {latest['intent_accuracy']*100:.1f}% and {latest['resolution_rate']*100:.0f}% of "
                 f"conversations resolve self-serve. Two things stand out - a hallucination spike to "
                 f"{halluc_peak*100:.1f}% around the day-22 incident (now recovered) and intent drift creeping up to "
                 f"{latest['intent_drift']*100:.0f}%."),
    "volume": latest["volume"],
    "intent_accuracy": latest["intent_accuracy"],
    "resolution_rate": latest["resolution_rate"],
    "hallucination_rate": latest["hallucination_rate"],
    "groundedness_rate": latest["groundedness_rate"],
    "p95_latency_ms": latest["p95_latency_ms"],
    "cost_per_resolved": latest["cost_per_resolved"],
    "intent_drift": latest["intent_drift"],
    "buckets": buckets_summary,
    "changes": [
        f"Hallucination risk spiked to {halluc_peak*100:.1f}% around day 22, recovered within ~3 days.",
        f"Intent accuracy drifted down {abs(intent_change)*100:.1f} pts over the window.",
        f"Intent drift rose {drift_change*100:.0f} pts to {latest['intent_drift']*100:.0f}% - watch closely.",
        f"New model shipped day {release_day}: small gains in accuracy and cache-hit rate.",
    ],
    "recommendation": ("Investigate the retrieval index refresh tied to the day-22 hallucination spike, and refresh "
                       "intent labels for Substitutions where drift is highest. Both are content/data fixes, not model "
                       "swaps - the cheapest lever with the biggest quality return."),
}

# ---- hero
art = (
    "<svg class='hero-art' width='152' height='106' viewBox='0 0 152 106' fill='none'>"
    "<circle cx='120' cy='38' r='58' fill='rgba(255,255,255,0.06)'/>"
    # signal line being observed
    "<path d='M12 76 L34 60 L48 68 L64 40 L80 52 L100 30 L130 38' stroke='rgba(255,255,255,0.55)' "
    "stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/>"
    # magnifier focusing on the peak
    "<circle cx='64' cy='46' r='24' fill='rgba(255,255,255,0.12)' stroke='#fff' stroke-width='3.4'/>"
    "<path d='M58 50 L64 36 L70 52' stroke='#fff' stroke-width='2.6' fill='none' "
    "stroke-linecap='round' stroke-linejoin='round'/>"
    "<line x1='82' y1='64' x2='98' y2='80' stroke='#fff' stroke-width='5' stroke-linecap='round'/>"
    "<circle cx='130' cy='38' r='4' fill='#22b892'/></svg>"
)
st.markdown(
    f"""
    <div class="hero">
      {art}
      <span class="pill">Model health . live operations view</span>
      <h1>Conversational AI Observability</h1>
      <p>How the customer-facing AI assistant is behaving in production - across quality,
      safety, performance, cost, and drift. <b>One screen to answer: is it healthy right now?</b></p>
      <div class="status-row">
        <div class="status"><div class="n">{latest['volume']:,}</div><div class="l">conversations today</div></div>
        <div class="status"><div class="n">{latest['intent_accuracy']*100:.1f}%</div><div class="l">intent accuracy</div></div>
        <div class="status"><div class="n">{latest['resolution_rate']*100:.0f}%</div><div class="l">resolved self-serve</div></div>
        <div class="status"><div class="n">{status}</div><div class="l">overall status</div></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["Executive summary", "Quality", "Safety", "Performance",
                "Cost", "Drift", "By domain", "Failure analysis", "Alerts",
                "Data pipeline"])

# ============================================================ EXEC SUMMARY
with tabs[0]:
    bul = "".join(f"<li>{esc(c)}</li>" for c in summary["changes"])
    st.markdown(
        f"""<div class='exec-card'>
        <h2>Executive summary</h2>
        <div class='lead'>{esc(summary['headline'])}</div>
        <div style='font-weight:800;font-family:Manrope;color:{SLATE_DK};margin-bottom:4px'>What changed</div>
        <ul>{bul}</ul>
        <div style='font-weight:800;font-family:Manrope;color:{SLATE_DK};margin:14px 0 4px'>Top recommendation</div>
        <div style='color:#454b5c;line-height:1.5'>{esc(summary['recommendation'])}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # bucket verdict chips
    chips = ""
    for b in buckets_summary:
        _, _, bg, fg = verdict_for(b["name"], b["ok"])
        label = "Healthy" if b["ok"] else "Watch"
        chips += (f"<div class='panel' style='margin-top:10px'><div class='bucket-verdict'>"
                  f"<span style='font-weight:800;font-family:Manrope;min-width:108px'>{esc(b['name'])}</span>"
                  f"<span class='chip' style='background:{bg};color:{fg}'>{label}</span></div>"
                  f"<div style='color:{MUTED};font-size:0.93rem;line-height:1.45'>{esc(b['verdict'])}</div></div>")
    st.markdown('<div class="section-title" style="margin-top:16px">Health by bucket</div>', unsafe_allow_html=True)
    st.markdown(chips, unsafe_allow_html=True)

    # ---- export row
    st.markdown('<div class="section-title" style="margin-top:18px">Share this report</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">Copy the summary for email, or download a formatted PDF or slide deck.</div>',
                unsafe_allow_html=True)
    summary_text = exec_summary_text(summary)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Copy executive summary", use_container_width=True):
            st.session_state["show_copy"] = True
    with c2:
        st.download_button("Download PDF report", data=build_pdf(summary),
                           file_name=f"ai-model-health-{date.today().isoformat()}.pdf",
                           mime="application/pdf", use_container_width=True)
    with c3:
        st.download_button("Download PowerPoint deck", data=build_pptx(summary),
                           file_name=f"ai-model-health-{date.today().isoformat()}.pptx",
                           mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                           use_container_width=True)
    if st.session_state.get("show_copy"):
        st.caption("Select all (Ctrl/Cmd+A) inside the box and copy, then paste into your email:")
        st.code(summary_text, language=None)

# ============================================================ helper to render a bucket
def render_bucket(title, intro, tiles_data, trends, takeaway, three=False,
                  expander=None):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-copy">{intro}</div>', unsafe_allow_html=True)
    tiles = [tile(*t) for t in tiles_data]
    st.markdown(grid(tiles, three=three), unsafe_allow_html=True)
    for i in range(0, len(trends), 2):
        cols = st.columns(2)
        for col, (name, key, color, fmt, band) in zip(cols, trends[i:i+2]):
            series = [d[key] for d in daily]
            with col:
                st.markdown(
                    f"<div class='panel'><div style='font-weight:700;font-family:Manrope;margin-bottom:6px'>{esc(name)}</div>"
                    f"{svg_sparkline(series, color=color, fmt=fmt, band=band, mark_incident=21, mark_release=release_day-1)}</div>",
                    unsafe_allow_html=True)
    if takeaway:
        st.markdown(f"<div class='takeaway'>{takeaway}</div>", unsafe_allow_html=True)
    if expander:
        with st.expander(expander[0]):
            st.markdown(expander[1])


# ============================================================ QUALITY
with tabs[1]:
    render_bucket(
        "Quality - is it understanding and resolving?",
        "Whether customers actually get their task done, not just whether a human was avoided.",
        [("Intent accuracy", f"{latest['intent_accuracy']*100:.1f}", "%", delta_html(latest['intent_accuracy'], prev['intent_accuracy']), "How often it understood the customer."),
         ("Resolution rate", f"{latest['resolution_rate']*100:.0f}", "%", delta_html(latest['resolution_rate'], prev['resolution_rate']), "Customer's task actually completed."),
         ("First-contact resolution", f"{latest['first_contact_resolution']*100:.0f}", "%", delta_html(latest['first_contact_resolution'], prev['first_contact_resolution']), "Solved without the customer coming back."),
         ("Repeat-contact rate", f"{latest['repeat_contact_rate']*100:.1f}", "%", delta_html(latest['repeat_contact_rate'], prev['repeat_contact_rate'], invert=True), "Same customer, same issue, within 48h.")],
        [("Intent accuracy", "intent_accuracy", SLATE, "{:.1%}", 0.93),
         ("Resolution rate", "resolution_rate", GREEN, "{:.1%}", 0.70),
         ("Unanswered rate", "unanswered_rate", AMBER, "{:.1%}", 0.08),
         ("CSAT", "csat", VIOLET, "{:.2f}", None)],
        f"Resolution ({latest['resolution_rate']*100:.0f}%) sits below containment ({latest['containment_rate']*100:.0f}%) - some conversations avoid a human but still don't solve the task. <b>That gap is where quality work pays off.</b>",
        expander=("Why resolution rate, not just containment?",
                  "**Containment** only means no human was involved. **Resolution** means the customer's task was actually completed. "
                  "A bot can look 'contained' while quietly failing customers - tracking resolution and repeat-contact catches that."),
    )

# ============================================================ SAFETY
with tabs[2]:
    render_bucket(
        "Safety - is it grounded and within policy?",
        "The trust signals: made-up detail, ungrounded claims, policy violations, and adversarial pressure.",
        [("Hallucination risk", f"{latest['hallucination_rate']*100:.1f}", "%", delta_html(latest['hallucination_rate'], prev['hallucination_rate'], invert=True), "Replies flagged for unsupported detail."),
         ("Groundedness", f"{latest['groundedness_rate']*100:.0f}", "%", delta_html(latest['groundedness_rate'], prev['groundedness_rate']), "Claims backed by a retrieved source."),
         ("Policy violations", f"{latest['policy_violation_rate']*100:.2f}", "%", delta_html(latest['policy_violation_rate'], prev['policy_violation_rate'], invert=True), "Toxic / non-compliant / out-of-scope replies."),
         ("Jailbreak attempts", f"{latest['jailbreak_attempts']}", "", delta_html(latest['jailbreak_attempts'], prev['jailbreak_attempts'], pct=False, invert=True), "Adversarial / prompt-injection attempts blocked.")],
        [("Hallucination risk", "hallucination_rate", RED, "{:.1%}", 0.04),
         ("Groundedness", "groundedness_rate", GREEN, "{:.1%}", 0.92),
         ("Policy-violation rate", "policy_violation_rate", AMBER, "{:.2%}", None),
         ("Refusal / over-refusal", "refusal_rate", VIOLET, "{:.1%}", 0.05)],
        f"Hallucination and groundedness move together - the day-22 spike to {max(d['hallucination_rate'] for d in daily)*100:.1f}% lined up with a groundedness dip. <b>Both point at retrieval, not the model.</b>",
        expander=("What's tracked under safety?",
                  "- **Groundedness / citation rate** - share of factual claims backed by a retrieved source.\n"
                  "- **Policy-violation rate** - toxic, non-compliant, or out-of-scope replies caught.\n"
                  "- **PII flags** - potential personal-data exposure caught by filters.\n"
                  "- **Jailbreak attempts** - adversarial / prompt-injection attempts detected and blocked."),
    )
    pii = [d["pii_flags"] for d in daily]
    st.markdown(f"<div class='panel'><div style='font-weight:700;font-family:Manrope;margin-bottom:6px'>PII flags per day</div>"
                f"{svg_sparkline(pii, color=AMBER, fmt='{:.0f}', mark_incident=21)}</div>", unsafe_allow_html=True)

# ============================================================ PERFORMANCE
with tabs[3]:
    render_bucket(
        "Performance - is it fast and reliable?",
        "Responsiveness and reliability - the operational health a platform owner watches alongside quality.",
        [("Median latency", f"{latest['latency_ms']:,.0f}", "ms", delta_html(latest['latency_ms'], prev['latency_ms'], pct=False, suffix=" ms", invert=True), "Typical time to a full response."),
         ("Time-to-first-token", f"{latest['ttft_ms']:,.0f}", "ms", delta_html(latest['ttft_ms'], prev['ttft_ms'], pct=False, suffix=" ms", invert=True), "Perceived responsiveness - first words out."),
         ("p95 latency", f"{latest['p95_latency_ms']:,.0f}", "ms", delta_html(latest['p95_latency_ms'], prev['p95_latency_ms'], pct=False, suffix=" ms", invert=True), "The slow tail (95th percentile)."),
         ("Uptime", f"{latest['uptime']*100:.2f}", "%", delta_html(latest['uptime'], prev['uptime']), "Availability over the day.")],
        [("Median latency (ms)", "latency_ms", SLATE, "{:,.0f}", None),
         ("Time-to-first-token (ms)", "ttft_ms", VIOLET, "{:,.0f}", None),
         ("p95 latency (ms)", "p95_latency_ms", RED, "{:,.0f}", 3000),
         ("Tool-call failure", "tool_failure_rate", AMBER, "{:.1%}", None)],
        "The day-22 incident shows up here too: latency jumped and the p95 tail breached the 3s SLA before recovering. <b>Latency and quality incidents often share a root cause.</b>",
    )

# ============================================================ COST
with tabs[4]:
    render_bucket(
        "Cost - is it economical per unit of value?",
        "Unit economics, normalized by success - cost only matters relative to the value delivered.",
        [("Cost / conversation", f"${latest['cost_per_convo']:.4f}", "", delta_html(latest['cost_per_convo'], prev['cost_per_convo'], pct=False, invert=True), "Model + tooling spend per conversation."),
         ("Cost / resolved", f"${latest['cost_per_resolved']:.4f}", "", delta_html(latest['cost_per_resolved'], prev['cost_per_resolved'], pct=False, invert=True), "Cost normalized by a resolved outcome."),
         ("Tokens / conversation", f"{latest['tokens_per_convo']:,}", "", delta_html(latest['tokens_per_convo'], prev['tokens_per_convo'], pct=False, invert=True), "The driver behind cost."),
         ("Cache-hit rate", f"{latest['cache_hit_rate']*100:.0f}", "%", delta_html(latest['cache_hit_rate'], prev['cache_hit_rate']), "Share served from cache (cheaper, faster).")],
        [("Cost per conversation ($)", "cost_per_convo", GREEN, "${:.4f}", None),
         ("Cost per resolved ($)", "cost_per_resolved", SLATE, "${:.4f}", None),
         ("Tokens per conversation", "tokens_per_convo", AMBER, "{:,.0f}", None),
         ("Cache-hit rate", "cache_hit_rate", VIOLET, "{:.0%}", None)],
        f"<b>Cost per resolved (${latest['cost_per_resolved']:.4f}) is the number that matters</b> - a cheap conversation that fails is more expensive than it looks. Cache-hit rose after the day-{release_day} model release.",
        expander=("Why cost-per-resolved?",
                  "Raw cost-per-conversation rewards cutting corners. **Cost per resolved** divides spend by successful "
                  "outcomes, so a model that's cheap but fails often looks correctly expensive. It's the cost metric tied to value."),
    )

# ============================================================ DRIFT
with tabs[5]:
    render_bucket(
        "Drift - is the world moving away from the model?",
        "Early-warning signals. Drift usually rises before accuracy falls - catching it early is the whole point.",
        [("Intent drift", f"{latest['intent_drift']*100:.0f}", "%", delta_html(latest['intent_drift'], prev['intent_drift'], invert=True), "Live intents vs the model's training set."),
         ("Topic drift", f"{latest['topic_drift']*100:.0f}", "%", delta_html(latest['topic_drift'], prev['topic_drift'], invert=True), "Are customers asking about new things?"),
         ("Quality drift", f"{latest['quality_drift']*100:.0f}", "%", delta_html(latest['quality_drift'], prev['quality_drift'], invert=True), "Is the score sliding over time?")],
        [("Intent drift", "intent_drift", SLATE, "{:.1%}", 0.15),
         ("Topic drift", "topic_drift", STEEL, "{:.1%}", 0.15),
         ("Quality drift", "quality_drift", RED, "{:.1%}", 0.10),
         ("Intent accuracy (for context)", "intent_accuracy", GREEN, "{:.1%}", None)],
        f"Intent drift climbed from {first['intent_drift']*100:.0f}% to {latest['intent_drift']*100:.0f}% over the month - and accuracy slipped in step. The purple line marks the day-{release_day} model release. <b>Drift is the leading indicator; accuracy is the lagging one.</b>",
        three=True,
        expander=("How drift connects to the model release",
                  f"A new model shipped on **day {release_day}** (purple marker). Pairing a drift chart with the release line "
                  "lets you attribute a step-change to a specific deployment - and tells you whether the new model helped or hurt."),
    )

# ============================================================ BY DOMAIN
with tabs[6]:
    st.markdown('<div class="section-title">Health by domain</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">The same assistant performs differently across journeys. This is where you spot which area needs investment next.</div>', unsafe_allow_html=True)
    rows = sorted(domains, key=lambda d: d["intent_accuracy"])
    body = ""
    for d in rows:
        ac = kpi_color(d["intent_accuracy"], True, 0.93, 0.88)
        hc = kpi_color(d["hallucination_rate"], False, 0.03, 0.05)
        cc = kpi_color(d["csat"], True, 4.2, 3.9)
        rc = kpi_color(d["resolution_rate"], True, 0.72, 0.64)
        body += (f"<tr><td style='font-weight:700'>{esc(d['domain'])}</td><td>{d['volume']:,}</td>"
                 f"<td><span class='badge' style='background:{ac}22;color:{ac}'>{d['intent_accuracy']*100:.1f}%</span></td>"
                 f"<td><span class='badge' style='background:{rc}22;color:{rc}'>{d['resolution_rate']*100:.0f}%</span></td>"
                 f"<td><span class='badge' style='background:{hc}22;color:{hc}'>{d['hallucination_rate']*100:.1f}%</span></td>"
                 f"<td>{d['groundedness_rate']*100:.0f}%</td>"
                 f"<td><span class='badge' style='background:{cc}22;color:{cc}'>{d['csat']:.2f}</span></td>"
                 f"<td>${d['cost_per_resolved']:.4f}</td><td>{d['intent_drift']*100:.0f}%</td></tr>")
    table = ("<table class='tbl'><thead><tr><th>Domain</th><th>Volume</th><th>Intent acc.</th>"
             "<th>Resolved</th><th>Halluc.</th><th>Grounded</th><th>CSAT</th><th>Cost/resolved</th><th>Drift</th>"
             "</tr></thead><tbody>" + body + "</tbody></table>")
    st.markdown(f"<div class='panel'>{table}</div>", unsafe_allow_html=True)
    worst = rows[0]
    st.markdown(f"<div class='takeaway'><b>{esc(worst['domain'])}</b> has the lowest intent accuracy ({worst['intent_accuracy']*100:.1f}%) - the clearest candidate for the next quality investment.</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title" style="margin-top:18px">Crowd-labeled vs predicted intent agreement</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">For top intents, how often human labels match the model. Low agreement flags an intent needing retraining.</div>', unsafe_allow_html=True)
    im = sorted(data["intent_matrix"], key=lambda x: x["agreement"])
    items = [(f"{r['intent']}  ({r['volume']:,}/day)", r["agreement"], kpi_color(r["agreement"], True, 0.9, 0.82)) for r in im]
    st.markdown(f"<div class='panel'>{svg_hbars(items, fmt='{:.0%}')}</div>", unsafe_allow_html=True)

# ============================================================ FAILURE ANALYSIS
with tabs[7]:
    st.markdown('<div class="section-title">When it fails, why?</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">Every poor or failed conversation, bucketed by root failure mode - turning "quality dropped" into "here\'s what to fix."</div>', unsafe_allow_html=True)
    fm = data["failure_modes"]
    palette = [RED, AMBER, SLATE, VIOLET, STEEL, "#c98a3a", "#7d8597", "#aab0bf"]
    items = [(m["mode"], m["share"], palette[i % len(palette)]) for i, m in enumerate(fm)]
    st.markdown(f"<div class='panel'>{svg_hbars(items, fmt='{:.0%}')}</div>", unsafe_allow_html=True)
    top = max(fm, key=lambda m: m["share"])
    st.markdown(f"<div class='takeaway'>The biggest single failure mode is <b>{esc(top['mode'].lower())}</b> at {top['share']*100:.0f}% - a knowledge-gap signal pointing at content/retrieval, not the model. <b>That's a different fix than a tone or intent problem.</b></div>", unsafe_allow_html=True)
    with st.expander("How would a PM act on this breakdown?"):
        st.markdown(
            "- **Missing knowledge** -> expand the knowledge base / retrieval coverage.\n"
            "- **Wrong intent** -> retrain or add examples for the confused intents.\n"
            "- **Tool/API failed** -> an engineering reliability fix, not a model change.\n"
            "- **Hallucinated detail** -> tighten grounding and the safety checker threshold.\n\n"
            "The breakdown routes each slice of failures to the team that can fix it.")

# ============================================================ ALERTS
with tabs[8]:
    st.markdown('<div class="section-title">Active alerts</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">What crossed a threshold and needs a human. Sorted by severity, tagged with the bucket it belongs to.</div>', unsafe_allow_html=True)
    order = {"critical": 0, "warning": 1, "info": 2}
    alerts = sorted(data["alerts"], key=lambda a: order.get(a["severity"], 9))
    out = ""
    for a in alerts:
        out += (f"<div class='alert {a['severity']}'><div class='dot'></div><div class='body'>"
                f"<div class='head'>{esc(a['metric'])}<span class='sev'>{esc(a['severity'])}</span> "
                f"<span style='font-size:0.7rem;color:{MUTED};font-weight:600'>&nbsp;{esc(a.get('bucket',''))}</span></div>"
                f"<div class='detail'>{esc(a['detail'])}</div><div class='where'>{esc(a['domain'])}</div></div></div>")
    st.markdown(out, unsafe_allow_html=True)
    st.markdown("<div class='takeaway'>In a real deployment these fire from automated threshold + anomaly checks and route to the owning team. Here they're illustrative, tied to the synthetic day-22 incident and the drift trend.</div>", unsafe_allow_html=True)

# ============================================================ DATA PIPELINE
with tabs[9]:
    st.markdown('<div class="section-title">How the data flows, end to end</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">This dashboard is backed by a real SQLite database, not a flat file. '
                'Raw conversation events are stored, then rolled up with SQL into the daily metrics and per-bucket '
                'summaries you see across the other tabs.</div>', unsafe_allow_html=True)

    # architecture flow
    steps = [
        ("1 . Ingest", "Conversation events", "Each conversation emits a row: intent correct?, resolved?, hallucinated?, latency, cost, CSAT."),
        ("2 . Store", "SQLite warehouse", f"{data['meta']['n_events']:,} raw events land in <code>conversation_events</code>, indexed by day and domain."),
        ("3 . Aggregate", "SQL rollups", "<code>GROUP BY</code> queries roll raw events into daily metrics, domain health, and failure shares."),
        ("4 . Serve", "Dashboard", "The five buckets, by-domain, and failure views all read these tables with SELECT queries."),
        ("5 . Act", "Alerts & exports", "Threshold queries raise alerts; the executive summary exports to PDF / PPTX."),
    ]
    flow = "<div style='display:flex;gap:10px;flex-wrap:wrap'>"
    for i, (n, t, d) in enumerate(steps):
        flow += (f"<div class='panel' style='flex:1;min-width:180px;margin-top:0'>"
                 f"<div style='font-size:0.72rem;font-weight:800;color:{SLATE};text-transform:uppercase;letter-spacing:0.05em'>{n}</div>"
                 f"<div style='font-weight:800;font-family:Manrope;margin:4px 0 6px'>{esc(t)}</div>"
                 f"<div style='color:{MUTED};font-size:0.84rem;line-height:1.4'>{d}</div></div>")
    flow += "</div>"
    st.markdown(flow, unsafe_allow_html=True)

    st.markdown('<div class="section-title" style="margin-top:20px">Schema</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-copy">Seven tables: one raw event stream plus six rollup / reference tables.</div>',
                unsafe_allow_html=True)
    st.code(
        "conversation_events  -- raw: one row per sampled conversation\n"
        "  (day, domain, intent_correct, resolved, contained, hallucinated,\n"
        "   grounded, escalated, latency_ms, ttft_ms, tokens, cost_usd, csat)\n\n"
        "daily_metrics        -- 30-day series, 29 metrics/day (pre-rolled)\n"
        "domain_health        -- current snapshot per domain\n"
        "failure_modes        -- failed-conversation breakdown by root cause\n"
        "intent_agreement     -- crowd-labeled vs predicted agreement\n"
        "alerts               -- threshold/anomaly alerts by severity & bucket\n"
        "meta                 -- window, model-release day, disclaimer",
        language="sql",
    )

    st.markdown('<div class="section-title" style="margin-top:18px">Live SQL rollup from raw events</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="section-copy">This table is computed at request time straight from the raw '
                '<code>conversation_events</code> stream - proof the pipeline is real, not pre-baked.</div>',
                unsafe_allow_html=True)
    st.code(
        "SELECT domain,\n"
        "       COUNT(*)                         AS convos,\n"
        "       ROUND(AVG(intent_correct)*100,1) AS intent_acc,\n"
        "       ROUND(AVG(resolved)*100,1)       AS resolved_pct,\n"
        "       ROUND(AVG(hallucinated)*100,2)   AS halluc_pct,\n"
        "       ROUND(AVG(latency_ms))           AS avg_latency\n"
        "FROM conversation_events\n"
        "GROUP BY domain\n"
        "ORDER BY intent_acc ASC;",
        language="sql",
    )
    rr = data["raw_rollup"]
    body = ""
    for r in rr:
        ac = kpi_color(r["intent_acc"] / 100, True, 0.93, 0.88)
        body += (f"<tr><td style='font-weight:700'>{esc(r['domain'])}</td>"
                 f"<td>{r['convos']:,}</td>"
                 f"<td><span class='badge' style='background:{ac}22;color:{ac}'>{r['intent_acc']:.1f}%</span></td>"
                 f"<td>{r['resolved_pct']:.1f}%</td><td>{r['halluc_pct']:.2f}%</td>"
                 f"<td>{r['avg_latency']:,.0f} ms</td></tr>")
    table = ("<table class='tbl'><thead><tr><th>Domain</th><th>Convos (sampled)</th>"
             "<th>Intent acc.</th><th>Resolved</th><th>Halluc.</th><th>Avg latency</th>"
             "</tr></thead><tbody>" + body + "</tbody></table>")
    st.markdown(f"<div class='panel'>{table}</div>", unsafe_allow_html=True)

    with st.expander("Reproduce the pipeline locally"):
        st.markdown(
            "```bash\n"
            "# 1. generate synthetic telemetry (JSON)\n"
            "python scripts/generate_telemetry.py\n\n"
            "# 2. build the SQLite database from it\n"
            "python scripts/build_database.py\n\n"
            "# 3. run the dashboard (reads telemetry.db via SQL)\n"
            "streamlit run streamlit_app.py\n"
            "```\n\n"
            "The committed `data/telemetry.db` is pre-built so the app deploys instantly - "
            "steps 1-2 are only needed to regenerate it."
        )

st.markdown(
    f"<div style='margin-top:26px;color:{MUTED};font-size:0.82rem'>"
    "All figures are fabricated for demonstration - no real traffic, models, or customers. "
    "A portfolio piece illustrating conversational-AI observability and model-health monitoring.</div>",
    unsafe_allow_html=True,
)
