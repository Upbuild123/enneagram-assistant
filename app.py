#!/usr/bin/env python3
"""
Enneagram Typing Assistant
Run with:
    source venv/bin/activate
    streamlit run app.py
"""
from __future__ import annotations

import os
import re
import sys
import json
import textwrap
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ── Env ────────────────────────────────────────────────────────────────────────
def _load_env() -> None:
    env = Path(__file__).parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

_load_env()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enneagram Typing Assistant",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 780px; }
.stApp { background-color: #ffffff; }

h1 { font-size: 1.7rem !important; font-weight: 700 !important; color: #111 !important; letter-spacing: -0.02em; }
h2, h3 { color: #111 !important; font-weight: 600 !important; }
p, li, span, label, .stMarkdown p { color: #333 !important; }
.stCaption, [data-testid="stCaptionContainer"], .stCaption p { color: #777 !important; font-size: 0.82rem !important; }

hr { border-color: #e5e7eb !important; margin: 1.4rem 0 !important; }

.step-label {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #666;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 0.12rem 0.5rem;
    margin-bottom: 0.5rem;
}

.stButton > button[kind="primary"] {
    background: #111 !important;
    border: none !important;
    color: #fff !important;
    font-weight: 600 !important;
    border-radius: 7px !important;
    padding: 0.5rem 1.2rem !important;
}
.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"] span {
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.82; }
.stButton > button[kind="primary"]:disabled { opacity: 0.3; }
.stButton > button:not([kind="primary"]) {
    background: #fff !important;
    border: 1px solid #d1d5db !important;
    color: #333 !important;
    border-radius: 7px !important;
    font-weight: 500 !important;
}
.stButton > button:not([kind="primary"]):hover { background: #f9fafb !important; }

.stTextInput > div > div > input, .stTextArea > div > div > textarea {
    background: #fff !important;
    border: 1px solid #d1d5db !important;
    border-radius: 7px !important;
    color: #111 !important;
    font-size: 0.88rem !important;
}
.stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
    border-color: #111 !important;
    box-shadow: 0 0 0 2px rgba(0,0,0,0.08) !important;
}

.stTextInput label, .stTextArea label { color: #333 !important; font-weight: 500 !important; }

.stTabs [data-baseweb="tab"] { color: #555 !important; }
.stTabs [aria-selected="true"] { color: #111 !important; border-bottom-color: #111 !important; }

/* Link table */
.link-row {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.4rem 0;
    border-bottom: 1px solid #f3f4f6;
    font-size: 0.87rem;
    color: #333;
}
.link-badge {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    padding: 0.12rem 0.45rem;
    border-radius: 4px;
    white-space: nowrap;
}
.badge-youtube   { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.badge-wikipedia { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
.badge-quotes    { background: #fefce8; color: #854d0e; border: 1px solid #fde68a; }
.badge-unknown   { background: #f9fafb; color: #6b7280; border: 1px solid #e5e7eb; }

/* Result cards */
.result-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 1rem;
}
.result-card h4 {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #111 !important;
    margin: 0 0 0.7rem 0;
}
.result-card .section-label {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #888;
    margin: 0.9rem 0 0.4rem 0;
}
.result-card ul { margin: 0; padding-left: 1.2rem; }
.result-card li { color: #333 !important; margin-bottom: 0.35rem; line-height: 1.55; font-size: 0.9rem; }
.result-card .error { color: #b91c1c !important; font-size: 0.88rem; }
</style>
""", unsafe_allow_html=True)

# ── URL helpers ────────────────────────────────────────────────────────────────
def _classify_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "wikipedia.org" in host:
        return "wikipedia"
    if any(q in host for q in ("brainyquote", "goodreads", "azquotes", "quotefancy",
                                "wikiquote", "quotes.net", "thefamouspeople")):
        return "quotes"
    return "unknown"

def _badge(kind: str) -> str:
    labels = {"youtube": "YouTube", "wikipedia": "Wikipedia",
              "quotes": "Quotes site", "unknown": "Unknown"}
    return f'<span class="link-badge badge-{kind}">{labels[kind]}</span>'

# ── Transcript fetching ────────────────────────────────────────────────────────
def _yt_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""

def _get_youtube_transcript(url: str) -> str | None:
    vid = _yt_video_id(url)
    if not vid:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        parts = YouTubeTranscriptApi.get_transcript(vid)
        return " ".join(p["text"] for p in parts)
    except Exception:
        pass
    # Fallback: yt-dlp subtitle download
    try:
        import subprocess, tempfile, glob
        with tempfile.TemporaryDirectory() as td:
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "--write-auto-sub", "--skip-download",
                "--sub-format", "vtt",
                "--output", f"{td}/sub",
                "--cookies-from-browser", "chrome",
                "--quiet", url,
            ]
            subprocess.run(cmd, timeout=60, capture_output=True)
            vtts = glob.glob(f"{td}/*.vtt")
            if vtts:
                raw = Path(vtts[0]).read_text(errors="ignore")
                lines = [l for l in raw.splitlines()
                         if l.strip() and not l.startswith("WEBVTT")
                         and not re.match(r"[\d:]+\s*-->\s*[\d:]+", l)
                         and not re.match(r"^\d+$", l.strip())]
                return " ".join(lines)
    except Exception:
        pass
    return None

def _get_webpage_text(url: str, max_chars: int = 12000) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return text[:max_chars]

# ── AI calls ───────────────────────────────────────────────────────────────────
def _ask(system: str, user: str, max_tokens: int = 900) -> str:
    if not client:
        return "Error: OPENAI_API_KEY not set."
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()

SYSTEM = (
    "You are a careful observer of human personality. "
    "You draw inferences from primary sources — what people say, how they say it, "
    "what they prioritize, how they handle pressure, what they reveal about themselves. "
    "You write clearly and specifically. You do not use jargon or impose frameworks."
)

def _personality_observations(text: str, source_hint: str, label: str) -> str:
    return _ask(SYSTEM, f"""\
From the {source_hint} below (titled "{label}"), infer who the subject is and list 6–12 \
personality observations as short bullet points.

Rules:
- Each bullet should be a short, direct observation (one sentence or less)
- Draw only from what is actually observable in the source
- Be willing to note both strengths and flaws, contradictions, blind spots, or uncomfortable patterns
- Do not name the person in the bullets
- Do not use phrases like "the subject", "they appear to", "seems to", or "suggests that"
- No intro line, no conclusion — just the bullets

Source:
---
{text[:10000]}
---""")

def _personality_quotes_yt(transcript: str, label: str) -> str:
    return _ask(SYSTEM, f"""\
From the transcript below (titled "{label}"), select the 5–10 most illuminating quotes.

- Attribute each quote by name if identifiable; use "Interviewer:" or "Narrator:" for others
- Lightly clean filler words but preserve voice
- One bullet per quote — no intro, no commentary

Transcript:
---
{transcript[:10000]}
---""", max_tokens=700)

def _quotes_from_page(text: str, label: str) -> str:
    return _ask(SYSTEM, f"""\
From the text below (titled "{label}"), select the 10–20 most illuminating quotes.

One bullet per quote. No intro, no commentary, no descriptions — just the quotes.

Text:
---
{text[:10000]}
---""", max_tokens=900)

# ── Link helpers ──────────────────────────────────────────────────────────────

def _links_from_text(text: str) -> list[dict]:
    seen, links = set(), []
    for line in text.splitlines():
        line = line.strip()
        url_match = re.search(r'https?://[^\s<>"\')\]]+', line)
        if not url_match:
            continue
        url = url_match.group(0).rstrip(".,;)")
        if url in seen:
            continue
        seen.add(url)
        # Try to extract a label from before the URL
        # Handles: "Title (3m3) — https://..." or "1. Title — https://..." or just the URL
        before = line[:url_match.start()].strip().rstrip("—–-").strip()
        before = re.sub(r'\(\d+m\d*s?\)\s*$', '', before).strip()  # strip (3m3), (54s)
        before = re.sub(r'^\d+\.\s*', '', before).strip()           # strip leading "1. "
        label  = before if before else url
        links.append({"url": url, "label": label})
    return links

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {"links": [], "results": []}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.title("🔍 Enneagram Typing Assistant")
st.caption("Paste links extracted from your email — the app processes each one and surfaces personality observations.")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — INPUT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="step-label">Step 1 — Paste links</div>', unsafe_allow_html=True)
st.caption("Open the email in your browser, use Claude's browser tool with the prompt **\"list all the links in this email with their URLs\"**, then paste the output below.")

raw = st.text_area("Links", placeholder="1999 Deep End of the Ocean Interview (3m3) — https://www.youtube.com/watch?v=...\nQuotes — https://www.brainyquote.com/...",
                   height=160, label_visibility="collapsed")
if st.button("Extract links", type="primary", use_container_width=True):
    found = _links_from_text(raw)
    if found:
        st.session_state.links = found
        st.success(f"{len(found)} links found.")
    else:
        st.warning("No URLs detected. Make sure each line contains a URL starting with https://")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — REVIEW + RUN
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="step-label">Step 2 — Review & Run</div>', unsafe_allow_html=True)
st.subheader("Links detected")

links = st.session_state.links
if not links:
    st.caption("No links yet — paste content above.")
else:
    rows = []
    for lk in links:
        kind    = _classify_url(lk["url"])
        label   = lk["label"] if lk["label"] != lk["url"] else ""
        display = (f"{label} — <span style='color:#6b7280;font-size:0.78rem'>{lk['url']}</span>"
                   if label else lk["url"])
        rows.append(
            f'<div class="link-row">{_badge(kind)}'
            f'<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{display}</span>'
            f'</div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)

    actionable = [lk for lk in links if _classify_url(lk["url"]) != "unknown"]
    skipped    = len(links) - len(actionable)
    if skipped:
        st.caption(f"{skipped} unknown link(s) will be skipped.")
    if not client:
        st.error("OPENAI_API_KEY not set in .env")

    if st.button(
        f"▶  Analyse  ({len(actionable)} link{'s' if len(actionable) != 1 else ''})",
        type="primary",
        use_container_width=True,
        disabled=not (actionable and client),
    ):
        results = []
        prog = st.progress(0.0)
        for i, lk in enumerate(actionable):
            kind  = _classify_url(lk["url"])
            label = lk["label"] if lk["label"] != lk["url"] else lk["url"]
            prog.progress(i / len(actionable), text=f"Processing: {label[:60]}")

            result = {"label": label, "url": lk["url"], "kind": kind,
                      "observations": None, "quotes": None, "error": None}
            try:
                if kind == "youtube":
                    transcript = _get_youtube_transcript(lk["url"])
                    if transcript:
                        result["observations"] = _personality_observations(transcript, "video transcript", label)
                        result["quotes"]       = _personality_quotes_yt(transcript, label)
                    else:
                        result["error"] = "Could not retrieve transcript."
                elif kind == "wikipedia":
                    text = _get_webpage_text(lk["url"])
                    result["observations"] = _personality_observations(text, "Wikipedia article", label)
                elif kind == "quotes":
                    text = _get_webpage_text(lk["url"])
                    result["quotes"] = _quotes_from_page(text, label)
            except Exception as e:
                result["error"] = str(e)

            results.append(result)

        prog.progress(1.0, text="Done")
        st.session_state.results = results
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ══════════════════════════════════════════════════════════════════════════════
def _copy_button(text: str, key: str) -> None:
    escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    import streamlit.components.v1 as components
    components.html(f"""
    <button onclick="navigator.clipboard.writeText(`{escaped}`).then(() => {{
        this.textContent = 'Copied!';
        setTimeout(() => this.textContent = 'Copy', 1500);
    }})" style="
        cursor:pointer; background:#fff; border:1px solid #d1d5db;
        border-radius:6px; padding:0.3rem 0.8rem; font-size:0.78rem;
        font-family:Inter,sans-serif; color:#333; font-weight:500;
    ">Copy</button>
    """, height=40)

if st.session_state.results:
    st.divider()
    st.markdown('<div class="step-label">Results</div>', unsafe_allow_html=True)
    st.subheader("Personality observations")

    for i, r in enumerate(st.session_state.results):
        # Build plain-text version for copy button
        plain_parts = [r["label"], r["url"]]
        if r.get("error"):
            plain_parts.append(f"Error: {r['error']}")
        else:
            if r.get("observations"):
                plain_parts.append("\nObservations:")
                plain_parts.append(r["observations"])
            if r.get("quotes"):
                plain_parts.append("\nQuotes:")
                plain_parts.append(r["quotes"])
        plain_text = "\n".join(plain_parts)

        # Card header
        st.markdown(
            f'<div class="result-card">'
            f'<h4>{r["label"]} <span style="font-weight:400;color:#888;font-size:0.8rem">· {r["kind"]}</span></h4>'
            f'</div>', unsafe_allow_html=True
        )

        with st.container():
            if r.get("error"):
                st.error(r["error"])
            else:
                if r.get("observations"):
                    st.markdown("**Observations**")
                    obs_lines = [l.strip() for l in r["observations"].splitlines() if l.strip()]
                    for line in obs_lines:
                        clean = re.sub(r'^[-•*]\s*', '', line)
                        st.markdown(f"- {clean}")

                if r.get("quotes"):
                    st.markdown("**Quotes**")
                    q_lines = [l.strip() for l in r["quotes"].splitlines() if l.strip()]
                    for line in q_lines:
                        clean = re.sub(r'^[-•*]\s*', '', line)
                        st.markdown(f"- {clean}")

            _copy_button(plain_text, key=f"copy_{i}")

        st.divider()

    if st.button("🗑  Clear results"):
        st.session_state.results = []
        st.rerun()
