"""Phase 6 (redesigned) — Streamlit chat UI.

Groww-inspired dark theme. Three-column layout:
  Left   (1 unit):   Clickable chat history + covered funds
  Center (2.5 units): Conversation + sticky chat input
  Right  (1.2 units): Fund Details panel

Session model: each Q&A is one entry {question, response, ts}.
Active session is displayed in center; all sessions listed in left column.

Run:
    streamlit run ui/streamlit_app.py
(Requires FastAPI backend on API_BASE, default http://localhost:8000)
"""
from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import urlparse

import requests
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
API_URL = f"{API_BASE}/api/chat"

EXAMPLE_QUESTIONS = [
    "What is the expense ratio of HDFC Mid Cap Fund?",
    "Who manages the HDFC Defence Fund?",
    "What is the exit load for HDFC Gold ETF Fund of Fund?",
]

COVERED_FUNDS = [
    "HDFC Mid Cap Fund",
    "HDFC Large Cap Fund",
    "HDFC Small Cap Fund",
    "HDFC Gold ETF FoF",
    "HDFC Defence Fund",
]

SECTION_LABELS: dict[str, str] = {
    "expense_ratio":        "Expense Ratio",
    "exit_load":            "Exit Load",
    "minimum_investment":   "Min Investment",
    "benchmark":            "Benchmark",
    "tax":                  "Taxation",
    "fund_management":      "Fund Management",
    "investment_objective": "Investment Objective",
    "fund_house":           "Fund House",
    "overview":             "Overview",
}

# ── Design tokens (Stitch "Terminal Precision" palette) ────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

/* ── Streamlit chrome reset ───────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {
    background-color: #0d1511 !important;
    color: #dce5de !important;
}
[data-testid="stHeader"], footer, #MainMenu { display: none !important; }
.block-container {
    padding-top: 0.75rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
}
/* Remove Streamlit's default white column backgrounds */
[data-testid="stVerticalBlock"] { background: transparent !important; }
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #3c4a43 !important;
    border-radius: 8px !important;
}
/* Text defaults */
p, li, span, label, div {
    color: #dce5de;
    font-family: 'Inter', sans-serif;
}
h1, h2, h3, h4, h5 {
    color: #dce5de !important;
    font-family: 'Geist', sans-serif !important;
}
/* Streamlit markdown paragraphs */
[data-testid="stMarkdownContainer"] p { color: #dce5de !important; }

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
    background: transparent !important;
    border: 1px solid #3c4a43 !important;
    color: #bacac1 !important;
    border-radius: 4px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 12.5px !important;
    text-align: left !important;
    transition: border-color 0.15s, color 0.15s, background 0.15s !important;
}
.stButton > button:hover {
    border-color: #44edb7 !important;
    color: #dce5de !important;
    background: rgba(68,237,183,0.04) !important;
}
/* Primary = active history item or New Chat */
.stButton > button[kind="primary"] {
    background: rgba(68,237,183,0.08) !important;
    border: 1px solid rgba(68,237,183,0.3) !important;
    color: #44edb7 !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: rgba(68,237,183,0.13) !important;
}

/* ── Chat input ───────────────────────────────────────────────────────────── */
[data-testid="stChatInput"] textarea {
    background: #161d19 !important;
    color: #dce5de !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    caret-color: #44edb7 !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #85948c !important; }
[data-testid="stChatInput"] button {
    background: #44edb7 !important;
    color: #0d1511 !important;
    border: none !important;
}

/* ── Status widget ────────────────────────────────────────────────────────── */
[data-testid="stStatusWidget"],
[data-testid="stStatusWidgetBody"] {
    background: #1a211d !important;
    border: 1px solid #3c4a43 !important;
    border-radius: 6px !important;
    color: #bacac1 !important;
}
[data-testid="stStatusWidget"] * { color: #bacac1 !important; font-family: 'Inter', sans-serif !important; }

/* ── Spinner ──────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] * { color: #44edb7 !important; }

/* ── Scrollbar inside fixed-height container ──────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d1511; }
::-webkit-scrollbar-thumb { background: #3c4a43; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #44edb7; }

/* ══ CUSTOM COMPONENTS ═══════════════════════════════════════════════════════ */

/* Left column header */
.lc-header {
    display: flex; align-items: center; justify-content: space-between;
    padding-bottom: 10px; margin-bottom: 10px;
    border-bottom: 1px solid #3c4a43;
}
.lc-logo {
    font-family: 'Geist', sans-serif; font-size: 14px; font-weight: 700;
    color: #44edb7; letter-spacing: -0.01em;
}

/* Section labels (left column dividers) */
.sec-lbl {
    font-family: 'Geist', sans-serif; font-size: 10px; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase; color: #85948c;
    padding: 10px 0 4px 0; border-top: 1px solid #3c4a43; margin-top: 4px;
}
.fund-item {
    font-family: 'Inter', sans-serif; font-size: 12px; color: #85948c;
    padding: 2px 0; display: block;
}

/* ── Landing state ────────────────────────────────────────────────────────── */
.landing {
    text-align: center; padding: 2.5rem 0.5rem 1.5rem;
}
.landing-h {
    font-family: 'Geist', sans-serif; font-size: 22px; font-weight: 700;
    color: #dce5de; letter-spacing: -0.02em; line-height: 1.3; margin-bottom: 6px;
}
.landing-h .g { color: #44edb7; }
.landing-sub {
    font-family: 'Inter', sans-serif; font-size: 13px; color: #85948c; margin-bottom: 20px;
}
.disc-chip {
    display: inline-block; font-family: 'Inter', sans-serif; font-size: 11px;
    color: #85948c; background: #1a211d; border: 1px solid #3c4a43;
    border-radius: 999px; padding: 3px 10px; margin-bottom: 1.2rem;
}

/* ── Chat bubbles ─────────────────────────────────────────────────────────── */

/* User bubble — right-aligned */
.u-row { display: flex; justify-content: flex-end; margin: 10px 0 4px; }
.u-bub {
    background: #242c28; border-radius: 16px 16px 3px 16px;
    padding: 9px 13px; max-width: 74%;
    color: #dce5de; font-family: 'Inter', sans-serif; font-size: 13.5px; line-height: 1.5;
}

/* Bot bubble — left-aligned */
.b-row { display: flex; gap: 9px; margin: 4px 0 10px; align-items: flex-start; }
.b-av {
    width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0; margin-top: 3px;
    background: rgba(68,237,183,0.08); border: 1px solid rgba(68,237,183,0.22);
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: #44edb7; font-family: 'Geist', sans-serif;
}
.b-card {
    flex: 1; background: #161d19; border: 1px solid #3c4a43;
    border-radius: 3px 16px 16px 16px; padding: 11px 13px;
}
.b-card.refusal { border-left: 3px solid #ffa15b; }
.b-ans {
    color: #dce5de; font-family: 'Inter', sans-serif;
    font-size: 13.5px; line-height: 1.7; margin-bottom: 0; white-space: pre-wrap;
}
.b-ans.muted { color: #bacac1; }

/* ── Citation + trust row ─────────────────────────────────────────────────── */
.cite-row {
    display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
    margin-top: 9px; padding-top: 9px; border-top: 1px solid #3c4a43;
}
.trust-chip {
    display: inline-flex; align-items: center; gap: 3px;
    font-family: 'Geist', sans-serif; font-size: 10px; font-weight: 600;
    color: #44edb7; background: rgba(68,237,183,0.08);
    border: 1px solid rgba(68,237,183,0.2); border-radius: 999px; padding: 2px 7px;
}
.cite-lnk {
    color: #44edb7; font-family: 'Inter', sans-serif; font-size: 12px;
    text-decoration: none; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; max-width: 260px;
}
.cite-lnk:hover { text-decoration: underline; }
.cite-sep { color: #3c4a43; }
.cite-date { color: #85948c; font-family: 'Inter', sans-serif; font-size: 11px; }

/* ── Why this answer? ─────────────────────────────────────────────────────── */
.why-wrap { margin-top: 8px; }
.why-wrap details > summary {
    font-family: 'Inter', sans-serif; font-size: 11px; color: #85948c;
    cursor: pointer; list-style: none; user-select: none;
}
.why-wrap details > summary::-webkit-details-marker { display: none; }
.why-wrap details > summary::before { content: "▸ "; font-size: 9px; }
.why-wrap details[open] > summary::before { content: "▾ "; }
.why-body {
    background: #0d1511; border: 1px solid #3c4a43; border-radius: 4px;
    padding: 8px 10px; margin-top: 5px;
}
.why-row { display: flex; gap: 8px; padding: 2.5px 0; font-size: 12px; }
.why-k {
    font-family: 'Geist', sans-serif; font-size: 10px; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase; color: #85948c;
    min-width: 58px; padding-top: 1px;
}
.why-v { font-family: 'Inter', sans-serif; color: #bacac1; }
.why-v a { color: #44edb7; text-decoration: none; font-size: 11px; }
.why-v a:hover { text-decoration: underline; }

/* ── Fund Details right panel ─────────────────────────────────────────────── */
.panel-hdr {
    font-family: 'Geist', sans-serif; font-size: 10px; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase; color: #85948c; margin-bottom: 8px;
}
.snap-ph {
    background: #161d19; border: 1px dashed #3c4a43; border-radius: 6px;
    padding: 20px 12px; text-align: center;
    font-family: 'Inter', sans-serif; font-size: 12px; color: #85948c; line-height: 1.6;
}
.snap-card { background: #161d19; border: 1px solid #3c4a43; border-radius: 6px; padding: 12px; }
.snap-name {
    font-family: 'Geist', sans-serif; font-size: 13px; font-weight: 600; color: #dce5de;
}
.snap-badge {
    display: inline-block; font-family: 'Geist', sans-serif; font-size: 9px; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase; color: #44edb7;
    background: rgba(68,237,183,0.1); border: 1px solid rgba(68,237,183,0.2);
    border-radius: 3px; padding: 1px 5px; margin-left: 6px; vertical-align: middle;
}
.snap-sub { font-family: 'Inter', sans-serif; font-size: 11px; color: #85948c; margin-top: 4px; }
.snap-div { border-top: 1px solid #3c4a43; margin: 9px 0; }
.snap-row { display: flex; justify-content: space-between; align-items: baseline; padding: 4px 0; }
.snap-lbl {
    font-family: 'Geist', sans-serif; font-size: 10px; font-weight: 600;
    letter-spacing: 0.05em; text-transform: uppercase; color: #85948c;
}
.snap-val { font-family: 'Inter', sans-serif; font-size: 12.5px; color: #dce5de; }
.snap-val.g { color: #44edb7; }
.snap-val a { color: #44edb7; text-decoration: none; font-size: 11.5px; }
.snap-val a:hover { text-decoration: underline; }
"""

# ── Page config ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="HDFC MF FAQ",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────

if "sessions" not in st.session_state:
    st.session_state.sessions: list[dict] = []
    # Each entry: {question: str, response: dict, ts: str}

if "active_idx" not in st.session_state:
    st.session_state.active_idx = None  # None = landing page

# ── Helpers ────────────────────────────────────────────────────────────────────

def call_api(message: str) -> dict:
    try:
        r = requests.post(API_URL, json={"message": message}, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {
            "answer": "Could not connect to the API. Ensure the backend is running on port 8000.",
            "citation_url": "", "last_updated": "", "is_refusal": True,
            "scheme_name": None, "section_intent": None,
        }
    except requests.exceptions.Timeout:
        return {
            "answer": "The request timed out. Please try again.",
            "citation_url": "", "last_updated": "", "is_refusal": True,
            "scheme_name": None, "section_intent": None,
        }
    except Exception as exc:
        return {
            "answer": f"Unexpected error: {exc}",
            "citation_url": "", "last_updated": "", "is_refusal": True,
            "scheme_name": None, "section_intent": None,
        }


def _short_url(url: str) -> str:
    """Return host + path for display, without scheme."""
    if not url:
        return ""
    try:
        p = urlparse(url)
        return (p.netloc + p.path).rstrip("/")
    except Exception:
        return url


def _fund_type(scheme_name: str) -> str:
    n = scheme_name.lower()
    if "gold" in n:
        return "COMMODITY"
    if "defence" in n or "sectoral" in n or "thematic" in n:
        return "SECTORAL"
    return "EQUITY"


def _strip_footer(answer: str) -> str:
    return answer.split("\n\nLast updated:")[0].strip()


def process_question(question: str) -> None:
    """Call API with real progress indicator, store result, activate session."""
    with st.status("Analyzing your question…", expanded=True) as s:
        s.write("🔍 Classifying question type…")
        s.write("📚 Searching fund knowledge base…")
        s.write("⚡ Generating answer…")
        response = call_api(question)
        done_label = "✓ Answer ready" if not response.get("is_refusal") else "Response ready"
        s.update(label=done_label, state="complete", expanded=False)

    st.session_state.sessions.append({
        "question": question,
        "response": response,
        "ts": datetime.now().strftime("%H:%M"),
    })
    st.session_state.active_idx = len(st.session_state.sessions) - 1
    st.rerun()


# ── Rendering functions ────────────────────────────────────────────────────────

def render_bot_bubble(response: dict) -> None:
    answer       = _strip_footer(response.get("answer", ""))
    citation_url = response.get("citation_url", "")
    last_updated = response.get("last_updated", "")
    is_refusal   = response.get("is_refusal", False)
    scheme_name  = response.get("scheme_name")
    section_intent = response.get("section_intent")

    card_cls = "b-card refusal" if is_refusal else "b-card"
    ans_cls  = "b-ans muted"   if is_refusal else "b-ans"

    # Citation + trust row
    cite_html = ""
    if citation_url:
        trust = "" if is_refusal else '<span class="trust-chip">✓ Source verified</span>'
        date_html = (
            f'<span class="cite-sep">·</span>'
            f'<span class="cite-date">Last updated: {last_updated}</span>'
            if last_updated and not is_refusal else ""
        )
        cite_html = (
            f'<div class="cite-row">'
            f'{trust}'
            f'<a class="cite-lnk" href="{citation_url}" target="_blank">'
            f'🔗 {_short_url(citation_url)}</a>'
            f'{date_html}'
            f'</div>'
        )

    # "Why this answer?" — collapsed by default
    why_html = ""
    if not is_refusal and (scheme_name or section_intent):
        sec_label = SECTION_LABELS.get(section_intent, section_intent) if section_intent else "—"
        rows = ""
        if scheme_name:
            rows += f'<div class="why-row"><span class="why-k">Scheme</span><span class="why-v">{scheme_name}</span></div>'
        if section_intent:
            rows += f'<div class="why-row"><span class="why-k">Section</span><span class="why-v">{sec_label}</span></div>'
        if citation_url:
            rows += (
                f'<div class="why-row"><span class="why-k">Source</span>'
                f'<span class="why-v"><a href="{citation_url}" target="_blank">{_short_url(citation_url)}</a></span></div>'
            )
        why_html = (
            f'<div class="why-wrap">'
            f'<details><summary>Why this answer?</summary>'
            f'<div class="why-body">{rows}</div>'
            f'</details></div>'
        )

    st.markdown(
        f'<div class="b-row">'
        f'<div class="b-av">◆</div>'
        f'<div class="{card_cls}">'
        f'<div class="{ans_cls}">{answer}</div>'
        f'{cite_html}'
        f'{why_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def render_fund_details(response: dict | None) -> None:
    st.markdown('<div class="panel-hdr">FUND DETAILS</div>', unsafe_allow_html=True)

    if (
        response is None
        or response.get("is_refusal")
        or not response.get("scheme_name")
    ):
        st.markdown(
            '<div class="snap-ph">Ask a factual question<br>to see fund details here.</div>',
            unsafe_allow_html=True,
        )
        return

    scheme_name    = response["scheme_name"]
    section_intent = response.get("section_intent")
    citation_url   = response.get("citation_url", "")
    last_updated   = response.get("last_updated", "")
    fund_type      = _fund_type(scheme_name)
    sec_label      = SECTION_LABELS.get(section_intent, "—") if section_intent else "—"

    date_row = (
        f'<div class="snap-row">'
        f'<span class="snap-lbl">Data as of</span>'
        f'<span class="snap-val">{last_updated}</span></div>'
        if last_updated else ""
    )
    src_row = (
        f'<div class="snap-row">'
        f'<span class="snap-lbl">Source</span>'
        f'<span class="snap-val"><a href="{citation_url}" target="_blank">'
        f'{urlparse(citation_url).netloc} ↗</a></span></div>'
        if citation_url else ""
    )

    st.markdown(
        f'<div class="snap-card">'
        f'<div class="snap-name">{scheme_name}'
        f'<span class="snap-badge">{fund_type}</span></div>'
        f'<div class="snap-sub">Direct Plan · Growth</div>'
        f'<div class="snap-div"></div>'
        f'<div class="snap-row"><span class="snap-lbl">Section</span>'
        f'<span class="snap-val g">{sec_label}</span></div>'
        f'{date_row}'
        f'{src_row}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Three-column layout ────────────────────────────────────────────────────────

col_left, col_center, col_right = st.columns([1, 2.5, 1.2], gap="small")

# ══ LEFT COLUMN ════════════════════════════════════════════════════════════════

with col_left:
    st.markdown(
        '<div class="lc-header"><span class="lc-logo">◆ HDFC MF FAQ</span></div>',
        unsafe_allow_html=True,
    )

    if st.button("＋ New Chat", use_container_width=True, type="primary", key="new_chat"):
        st.session_state.active_idx = None
        st.rerun()

    sessions   = st.session_state.sessions
    active_idx = st.session_state.active_idx

    if sessions:
        st.markdown('<div class="sec-lbl">HISTORY</div>', unsafe_allow_html=True)
        # Show most recent first
        for i in range(len(sessions) - 1, -1, -1):
            q = sessions[i]["question"]
            label = q if len(q) <= 38 else q[:38] + "…"
            is_active = i == active_idx
            if st.button(
                label,
                key=f"hist_{i}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.active_idx = i
                st.rerun()

    st.markdown('<div class="sec-lbl">COVERED FUNDS</div>', unsafe_allow_html=True)
    for name in COVERED_FUNDS:
        st.markdown(f'<span class="fund-item">· {name}</span>', unsafe_allow_html=True)

# ══ CENTER COLUMN ══════════════════════════════════════════════════════════════

with col_center:
    active_idx = st.session_state.active_idx
    sessions   = st.session_state.sessions

    # Guard: stale index after clear
    if active_idx is not None and active_idx >= len(sessions):
        st.session_state.active_idx = None
        active_idx = None

    DISC = (
        '<div style="text-align:center;margin-bottom:10px;">'
        '<span class="disc-chip">⚠️ Facts-only · No investment advice</span>'
        '</div>'
    )

    if active_idx is None:
        # ── Landing / empty state ──────────────────────────────────────────────
        st.markdown(
            '<div class="landing">'
            '<div class="landing-h">Ask anything about your<br>'
            '<span class="g">HDFC Mutual Fund</span></div>'
            '<div class="landing-sub">'
            'Factual answers about expense ratios, exit loads, fund managers, and more.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(DISC, unsafe_allow_html=True)

        # Example question chips (rendered as Streamlit buttons styled by CSS)
        eg_cols = st.columns(len(EXAMPLE_QUESTIONS))
        for col, q in zip(eg_cols, EXAMPLE_QUESTIONS):
            with col:
                if st.button(q, use_container_width=True):
                    process_question(q)

    else:
        # ── Conversation view ──────────────────────────────────────────────────
        session = sessions[active_idx]

        with st.container(height=490, border=False):
            st.markdown(DISC, unsafe_allow_html=True)

            # User bubble
            st.markdown(
                f'<div class="u-row"><div class="u-bub">{session["question"]}</div></div>',
                unsafe_allow_html=True,
            )

            # Bot bubble
            if "response" in session:
                render_bot_bubble(session["response"])

    # ── Chat input — always rendered, sticky at column bottom ─────────────────
    user_input = st.chat_input("Ask about an HDFC fund scheme…")
    if user_input and user_input.strip():
        process_question(user_input.strip())

# ══ RIGHT COLUMN ═══════════════════════════════════════════════════════════════

with col_right:
    active_idx = st.session_state.active_idx
    sessions   = st.session_state.sessions

    panel_resp: dict | None = None
    if active_idx is not None and active_idx < len(sessions):
        panel_resp = sessions[active_idx].get("response")

    render_fund_details(panel_resp)
