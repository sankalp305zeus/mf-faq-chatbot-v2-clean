"""Phase 6 — Streamlit chat UI.

Facts-only mutual fund FAQ assistant for HDFC schemes.

Connects to the FastAPI backend at API_BASE (default http://localhost:8000).
Override API_BASE env var for Railway / production deployments.

Run locally (after starting FastAPI on port 8000):
    streamlit run ui/streamlit_app.py
"""
from __future__ import annotations

import os

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

# ── Page setup ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="HDFC MF FAQ Assistant",
    page_icon="📊",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .disclaimer-banner {
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 6px;
        padding: 10px 16px;
        font-size: 0.9rem;
        color: #856404;
        margin-bottom: 1rem;
    }
    .answer-box {
        background-color: #f8f9fa;
        border-left: 4px solid #198754;
        border-radius: 4px;
        padding: 12px 16px;
        margin-top: 0.5rem;
        font-size: 0.95rem;
    }
    .refusal-box {
        background-color: #fff8f0;
        border-left: 4px solid #fd7e14;
        border-radius: 4px;
        padding: 12px 16px;
        margin-top: 0.5rem;
        font-size: 0.95rem;
        color: #6c3b00;
    }
    .citation-line {
        font-size: 0.82rem;
        color: #555;
        margin-top: 8px;
    }
    .footer-line {
        font-size: 0.78rem;
        color: #888;
        margin-top: 4px;
    }
    .user-msg {
        background-color: #e8f4fd;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 4px;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Disclaimer banner ──────────────────────────────────────────────────────────

st.markdown(
    '<div class="disclaimer-banner">'
    "⚠️ <strong>Facts-only. No investment advice.</strong> "
    "This assistant answers verifiable questions about HDFC mutual fund scheme details only. "
    "It does not provide investment recommendations, fund comparisons, or return projections."
    "</div>",
    unsafe_allow_html=True,
)

# ── Header ─────────────────────────────────────────────────────────────────────

st.title("HDFC Mutual Fund FAQ")
st.caption(
    "Ask factual questions about 5 HDFC schemes: "
    "Mid Cap · Large Cap · Small Cap · Gold ETF FoF · Defence Fund"
)

# ── Session state ──────────────────────────────────────────────────────────────

if "history" not in st.session_state:
    st.session_state.history = []  # list of {"role": "user"|"assistant", "content": dict|str}

if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""

# ── Example question buttons ───────────────────────────────────────────────────

if not st.session_state.history:
    st.markdown("**Try an example question:**")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for col, question in zip(cols, EXAMPLE_QUESTIONS):
        with col:
            if st.button(question, use_container_width=True):
                st.session_state.pending_question = question
                st.rerun()

# ── API call ───────────────────────────────────────────────────────────────────

def call_api(message: str) -> dict:
    try:
        resp = requests.post(API_URL, json={"message": message}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {
            "answer": "Could not connect to the backend. Please make sure the API server is running.",
            "citation_url": "",
            "last_updated": "",
            "is_refusal": True,
        }
    except requests.exceptions.Timeout:
        return {
            "answer": "The request timed out. Please try again.",
            "citation_url": "",
            "last_updated": "",
            "is_refusal": True,
        }
    except Exception as exc:
        return {
            "answer": f"Unexpected error: {exc}",
            "citation_url": "",
            "last_updated": "",
            "is_refusal": True,
        }


# ── Render a single assistant response ────────────────────────────────────────

def render_response(data: dict) -> None:
    answer = data.get("answer", "")
    citation_url = data.get("citation_url", "")
    last_updated = data.get("last_updated", "")
    is_refusal = data.get("is_refusal", False)

    # Strip the footer from answer text (formatter appends it; we render it separately)
    answer_body = answer.split("\n\nLast updated:")[0].strip()

    if is_refusal:
        st.markdown(
            f'<div class="refusal-box">{answer_body}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="answer-box">{answer_body}</div>',
            unsafe_allow_html=True,
        )

    if citation_url:
        st.markdown(
            f'<div class="citation-line">📎 Source: <a href="{citation_url}" target="_blank">{citation_url}</a></div>',
            unsafe_allow_html=True,
        )

    if last_updated and not is_refusal:
        st.markdown(
            f'<div class="footer-line">Last updated: {last_updated}</div>',
            unsafe_allow_html=True,
        )


# ── Chat history ───────────────────────────────────────────────────────────────

for turn in st.session_state.history:
    if turn["role"] == "user":
        st.markdown(
            f'<div class="user-msg">🧑 {turn["content"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        render_response(turn["content"])

# ── Input form ─────────────────────────────────────────────────────────────────

with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input(
        "Ask a question about an HDFC scheme",
        value=st.session_state.pending_question,
        placeholder="e.g. What is the exit load for HDFC Small Cap Fund?",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Ask", use_container_width=True)

if submitted and user_input.strip():
    question = user_input.strip()
    st.session_state.pending_question = ""

    st.session_state.history.append({"role": "user", "content": question})

    with st.spinner("Looking up answer…"):
        response = call_api(question)

    st.session_state.history.append({"role": "assistant", "content": response})
    st.rerun()

elif st.session_state.pending_question and not submitted:
    # Triggered by example button click — auto-submit on next rerun
    question = st.session_state.pending_question
    st.session_state.pending_question = ""

    st.session_state.history.append({"role": "user", "content": question})

    with st.spinner("Looking up answer…"):
        response = call_api(question)

    st.session_state.history.append({"role": "assistant", "content": response})
    st.rerun()

# ── Clear history ──────────────────────────────────────────────────────────────

if st.session_state.history:
    if st.button("Clear chat", type="secondary"):
        st.session_state.history = []
        st.rerun()
