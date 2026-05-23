"""
Streamlit 可视化面板 — Reddit 需求雷达 (Warm-Forum Redesign).
启动：streamlit run ui/app.py
"""
import datetime
import html
import os
import sys
import threading
from datetime import timezone
from urllib.parse import urlparse

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

import streamlit as st
from db.database import get_connection
from export.markdown import generate_report
from pipeline.service import run_pipeline
from settings import get_config_value, get_int_config

st.set_page_config(page_title="Reddit 需求雷达", layout="wide")

# ── Global Styles ──────────────────────────────────────────────────────────

_CSS = """
<style>
    /* ── Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

    /* ── Base ── */
    .stApp {
        background: #faf8f5;
    }
    [data-testid="stAppViewContainer"] > .main .block-container {
        max-width: 1180px;
        padding: 48px 48px 64px;
    }
    section[data-testid="stSidebar"] {
        background: #f5f2ed;
        border-right: 1px solid #e6e3dd;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stSlider label,
    section[data-testid="stSidebar"] .stSelectbox label {
        font-family: 'IBM Plex Sans', sans-serif !important;
    }

    /* ── Typography ── */
    h1, h2, h3, .big-title {
        font-family: 'Newsreader', serif !important;
        font-weight: 500 !important;
        color: #1a1a1a !important;
        letter-spacing: -0.01em;
    }
    p, span, div, label, .stMarkdown {
        font-family: 'IBM Plex Sans', sans-serif !important;
    }
    .st-caption {
        font-family: 'Newsreader', serif !important;
        font-style: italic;
        color: #8c8c8c !important;
    }
    .hero-spacer-top {
        height: 10vh;
    }
    .hero-title {
        text-align: center;
        margin-bottom: 10px;
    }
    .hero-title span {
        display: inline-block;
        font-family: Newsreader, serif;
        font-size: 64px;
        font-weight: 500;
        line-height: 1.05;
        color: #1a1a1a;
        letter-spacing: 0;
        white-space: nowrap;
        word-break: keep-all;
    }
    .hero-subtitle {
        text-align: center;
        margin-bottom: 36px;
    }
    .hero-subtitle span {
        font-family: Newsreader, serif;
        font-style: italic;
        font-size: 18px;
        color: #b0aca5;
        white-space: nowrap;
        word-break: keep-all;
    }
    @media (max-width: 900px) {
        [data-testid="stAppViewContainer"] > .main .block-container {
            padding: 36px 28px 56px;
        }
        .hero-title span {
            font-size: 52px;
        }
    }
    @media (max-width: 640px) {
        [data-testid="stAppViewContainer"] > .main .block-container {
            padding: 28px 18px 48px;
        }
        .hero-spacer-top {
            height: 6vh;
        }
        .hero-title span {
            font-size: 36px;
        }
        .hero-subtitle span {
            font-size: 14px;
        }
    }

    /* ── Remove Streamlit chrome ── */
    #MainMenu, header[data-testid="stHeader"], .stDeployButton,
    [data-testid="stDecoration"], .stAppToolbar {
        display: none !important;
    }
    footer { visibility: hidden; }

    /* ── Buttons ── */
    .stButton > button {
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-weight: 500 !important;
        border-radius: 4px !important;
        border: 1.5px solid #1a1a1a !important;
        background: #1a1a1a !important;
        color: #faf8f5 !important;
        padding: 10px 24px !important;
        transition: all 0.15s ease !important;
        letter-spacing: 0.02em;
    }
    .stButton > button:hover {
        background: #3d3d3d !important;
        border-color: #3d3d3d !important;
    }

    /* ── Inputs ── */
    .stTextInput input,
    .stNumberInput input {
        font-family: 'IBM Plex Sans', sans-serif !important;
        border-radius: 4px !important;
        border: 1.5px solid #d9d5ce !important;
        background: #fffdf9 !important;
        padding: 12px 16px !important;
        font-size: 16px !important;
        transition: border-color 0.15s ease !important;
    }
    .stTextInput input:focus,
    .stNumberInput input:focus {
        border-color: #1a1a1a !important;
        box-shadow: none !important;
    }
    .stTextInput label,
    .stSelectbox label,
    .stNumberInput label {
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #6f6a62 !important;
        margin-bottom: 7px !important;
    }
    .stSelectbox [data-baseweb="select"] > div {
        border-radius: 4px !important;
        background: #f3f3f0 !important;
        min-height: 52px !important;
    }
    .stTextInput [data-testid="stWidgetInstructions"],
    .stTextInput [data-testid="InputInstructions"],
    .stNumberInput [data-testid="stWidgetInstructions"],
    .stNumberInput [data-testid="InputInstructions"],
    .stTextInput div[aria-live="polite"],
    .stNumberInput div[aria-live="polite"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }
    .stNumberInput input::-webkit-outer-spin-button,
    .stNumberInput input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    .stNumberInput input {
        -moz-appearance: textfield;
    }
    .stNumberInput button {
        display: none !important;
    }
    .field-label {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 13px;
        font-weight: 600;
        color: #6f6a62;
        margin-bottom: 7px;
    }
    .field-label-note {
        color: #b0aca5;
        font-weight: 500;
    }
    .result-summary {
        display: inline-block;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 14px;
        line-height: 1.7;
        color: #6f6a62;
        margin: 18px 0 8px;
    }
    .result-summary strong {
        color: #1a1a1a;
        font-weight: 600;
    }
    .result-summary .muted {
        color: #b0aca5;
        margin: 0 7px;
    }

    /* ── Sliders ── */
    .stSlider [data-testid="stThumbValue"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
        background: #1a1a1a !important;
        color: #faf8f5 !important;
    }

    /* ── Expanders ── */
    .st-expander {
        border: 1px solid #e8e5df !important;
        border-radius: 4px !important;
        background: #fffdf9 !important;
        margin-bottom: 8px !important;
        box-shadow: none !important;
    }
    .st-expander:hover {
        border-color: #d0ccc4 !important;
    }
    /* Title bar */
    .st-expander > summary {
        font-family: 'Newsreader', serif !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        color: #1a1a1a !important;
        padding: 10px 12px !important;
        list-style: none !important;
    }
    .st-expander > summary::-webkit-details-marker {
        display: none !important;
    }
    .st-expander > summary::marker {
        display: none !important;
        content: none !important;
    }
    /* Hide the expander toggle icon */
    [data-testid="stExpanderIcon"] {
        display: none !important;
    }
    [data-testid="stExpanderToggleIcon"] {
        display: none !important;
    }
    /* Hide any SVG or icon inside summary */
    .st-expander > summary svg,
    .st-expander > summary i,
    .st-expander > summary span[class*="icon"] {
        display: none !important;
    }
    /* Content area */
    .st-expander [data-testid="stExpanderDetails"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
        color: #3d3d3d !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetricValue"] {
        font-family: 'Newsreader', serif !important;
        font-weight: 600 !important;
        font-size: 28px !important;
        color: #1a1a1a !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-size: 13px !important;
        color: #8c8c8c !important;
    }

    /* ── Info / Warning / Success ── */
    .stAlert {
        font-family: 'IBM Plex Sans', sans-serif !important;
        border-radius: 4px !important;
        border: 1px solid #e8e5df !important;
    }

    /* ── Download button ── */
    .stDownloadButton > button {
        font-family: 'IBM Plex Sans', sans-serif !important;
        border-radius: 4px !important;
        border: 1.5px solid #1a1a1a !important;
        background: transparent !important;
        color: #1a1a1a !important;
    }
    .stDownloadButton > button:hover {
        background: #f0ede7 !important;
    }

    /* ── Divider ── */
    hr {
        border-color: #e8e5df !important;
    }

    /* ── Post Cards (native <details>) ── */
    details.post-card {
        border: 1px solid #e8e5df;
        border-radius: 4px;
        background: #fffdf9;
        margin-bottom: 0;
    }
    details.post-card:hover {
        border-color: #d0ccc4;
    }
    details.post-card[open] {
        border-color: #c5c0b7;
    }
    details.post-card > summary.post-title {
        font-family: 'Newsreader', serif;
        font-weight: 600;
        font-size: 16px;
        color: #1a1a1a;
        padding: 12px 14px;
        cursor: pointer;
        list-style: none;
        outline: none;
    }
    details.post-card > summary.post-title::-webkit-details-marker {
        display: none;
    }
    details.post-card > summary.post-title::marker {
        display: none;
        content: none;
    }
    .title-meta-inline {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 13px;
        font-weight: 600;
        color: #8c8c8c;
        margin-right: 10px;
        white-space: nowrap;
    }
    .title-text-inline {
        color: #1a1a1a;
    }
    .post-meta {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 13px;
        color: #8c8c8c;
        padding: 0 14px 10px;
    }
    .post-body {
        display: flex;
        gap: 24px;
        padding: 0 14px 12px;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 14px;
        color: #3d3d3d;
        line-height: 1.6;
    }
    .post-col {
        flex: 1;
        min-width: 0;
    }
    .detail-label {
        font-weight: 600;
        font-size: 12px;
        color: #8c8c8c;
        margin-top: 8px;
        margin-bottom: 2px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .detail-text {
        color: #3d3d3d;
    }
    .detail-quote {
        color: #8c8c8c;
        font-style: italic;
        font-family: 'Newsreader', serif;
        font-size: 15px;
        border-left: 2px solid #e8e5df;
        padding-left: 12px;
        margin: 4px 0;
    }
    .detail-reason {
        color: #8c8c8c;
        font-size: 13px;
        margin-bottom: 4px;
    }
    .detail-link {
        display: inline-block;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 13px;
        color: #1a1a1a;
        text-decoration: underline;
        text-underline-offset: 3px;
        padding: 0 14px 8px;
    }
    .detail-link:hover {
        color: #3d3d3d;
    }
    .detail-conf {
        font-family: 'Newsreader', serif;
        font-style: italic;
        font-size: 13px;
        color: #b0aca5;
        padding: 0 14px 10px;
    }
</style>
"""

# ── Helpers ─────────────────────────────────────────────────────────────────

def _inject_styles():
    st.markdown(_CSS, unsafe_allow_html=True)


def _text(value, fallback="-"):
    if value is None or value == "":
        return fallback
    return str(value)


def _escape_html(value, fallback="-"):
    return html.escape(_text(value, fallback), quote=True)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_int(value, minimum=0, maximum=5, default=0):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _safe_external_url(value):
    url = _text(value, "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return html.escape(url, quote=True)


def _normalize_reddit_ids(reddit_ids):
    if reddit_ids is None:
        return None
    return list(dict.fromkeys(str(reddit_id) for reddit_id in reddit_ids if reddit_id))


def load_analyzed_posts(
    min_score=0,
    max_difficulty=5,
    subreddits=None,
    sort_by="priority",
    since=None,
    reddit_ids=None,
):
    conn = get_connection()
    conditions = ["analysis_status = 'analyzed'"]
    params = []
    normalized_ids = _normalize_reddit_ids(reddit_ids)
    if normalized_ids is not None:
        if not normalized_ids:
            conn.close()
            return []
        placeholders = ",".join(["?"] * len(normalized_ids))
        conditions.append(f"reddit_id IN ({placeholders})")
        params.extend(normalized_ids)
    elif since:
        conditions.append("scraped_at > ?")
        params.append(since)
    if min_score > 0:
        conditions.append("filter_score >= ?")
        params.append(min_score)
    if max_difficulty < 5:
        conditions.append("difficulty <= ?")
        params.append(max_difficulty)
    if subreddits:
        placeholders = ",".join(["?" for _ in subreddits])
        conditions.append(f"subreddit IN ({placeholders})")
        params.extend(subreddits)

    where = " AND ".join(conditions)
    order = {
        "score": "ORDER BY filter_score DESC",
        "difficulty": "ORDER BY difficulty ASC",
    }.get(sort_by, "ORDER BY (filter_score * 0.7 + (6 - COALESCE(difficulty, 5)) * 0.6) DESC")

    rows = conn.execute(f"SELECT * FROM posts WHERE {where} {order}", params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats(min_score=0, max_difficulty=5, subreddits=None, since=None, reddit_ids=None):
    conn = get_connection()
    conditions = ["analysis_status = 'analyzed'"]
    params = []
    normalized_ids = _normalize_reddit_ids(reddit_ids)
    if normalized_ids is not None:
        if not normalized_ids:
            conn.close()
            return {
                "total": 0,
                "avg_score": 0.0,
                "high_priority": 0,
                "os_count": 0,
            }
        placeholders = ",".join(["?"] * len(normalized_ids))
        conditions.append(f"reddit_id IN ({placeholders})")
        params.extend(normalized_ids)
    elif since:
        conditions.append("scraped_at > ?")
        params.append(since)
    if min_score > 0:
        conditions.append("filter_score >= ?")
        params.append(min_score)
    if max_difficulty < 5:
        conditions.append("difficulty <= ?")
        params.append(max_difficulty)
    if subreddits:
        placeholders = ",".join(["?"] * len(subreddits))
        conditions.append(f"subreddit IN ({placeholders})")
        params.extend(subreddits)
    where = " AND ".join(conditions)

    total = conn.execute(f"SELECT COUNT(*) FROM posts WHERE {where}", params).fetchone()[0]
    avg_score = conn.execute(f"SELECT AVG(filter_score) FROM posts WHERE {where}", params).fetchone()[0]
    high_priority = conn.execute(
        f"SELECT COUNT(*) FROM posts WHERE {where} AND difficulty <= 3 AND filter_score >= 7", params
    ).fetchone()[0]
    os_count = conn.execute(
        f"SELECT COUNT(*) FROM posts WHERE {where} AND opensource_value = 'high'", params
    ).fetchone()[0]
    conn.close()
    return {
        "total": total,
        "avg_score": round(avg_score, 1) if avg_score else 0.0,
        "high_priority": high_priority,
        "os_count": os_count,
    }


def _render_loading(stage, detail, progress_pct=0):
    icons = {"scraping": "⊷", "filtering": "⊶", "analyzing": "⊹"}
    icon = icons.get(stage, "⊙")
    safe_detail = _escape_html(detail, "")
    bar = "▰" * int(progress_pct / 10) + "▱" * (10 - int(progress_pct / 10))
    return f"""
    <div style="
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        padding: 80px 20px; text-align: center;
    ">
        <div style="
            font-size: 64px; margin-bottom: 28px; color: #1a1a1a;
            animation: forumPulse 2s ease-in-out infinite;
        ">{icon}</div>
        <div style="font-family: 'Newsreader', serif; font-size: 22px; color: #1a1a1a;
                    font-weight: 500; margin-bottom: 8px;">{safe_detail}</div>
        <div style="font-family: 'IBM Plex Sans', monospace; font-size: 14px; color: #b0aca5;
                    letter-spacing: 0.15em; margin-bottom: 20px;">{bar}</div>
        <p style="font-family: 'Newsreader', serif; font-style: italic; color: #b0aca5; font-size: 15px;">
            扫描 Reddit · 过滤噪音 · 提取洞察
        </p>
    </div>
    <style>
        @keyframes forumPulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.45; transform: scale(0.92); }}
        }}
    </style>
    """


def _difficulty_stars(n):
    stars = _plain_stars(n)
    filled = stars.replace("☆", "")
    empty = "☆" * (5 - len(filled))
    return f'<span style="color:#1a1a1a;">{filled}</span><span style="color:#d9d5ce;">{empty}</span>'


def _plain_stars(n):
    n = _clamp_int(n, 0, 5, 0)
    return "★" * n + "☆" * (5 - n)


def _rating_from_level(value):
    normalized = _text(value, "").strip().lower()
    mapping = {
        "high": 5,
        "medium": 3,
        "low": 1,
        "高": 5,
        "中": 3,
        "低": 1,
    }
    if normalized in mapping:
        return mapping[normalized]
    return _clamp_int(normalized, 0, 5, 0)


def _free_build_label(value):
    normalized = _text(value, "").strip().lower()
    mapping = {
        "yes": "基本可免费实现",
        "partial": "部分可免费实现",
        "no": "较难免费实现",
    }
    return mapping.get(normalized, "暂无数据")


def _safe_count(stats, key):
    try:
        return int((stats or {}).get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _empty_result_notice(stats):
    failed = _safe_count(stats, "failed")
    filtered_out = _safe_count(stats, "filtered_out")
    fetched = _safe_count(stats, "fetched")
    if failed > 0:
        return (
            "error",
            f"本次 AI 分析失败 {failed} 条。请检查 DeepSeek API Key、余额、网络连接，"
            "或稍后重试；这通常不是关键词问题。",
        )
    if filtered_out > 0:
        return (
            "info",
            f"本次抓到 {fetched} 条帖子，但 AI 判断暂时没有足够明确的痛点。可以换更具体的关键词试试。",
        )
    return ("info", "本次未获得新的分析洞察。换个关键词试试？")


def _job_set(job, **updates):
    with job["lock"]:
        job.update(updates)


def _job_snapshot(job):
    with job["lock"]:
        return dict(job)


def _clamp_search_limit():
    value = st.session_state.get("hero_limit")
    if value is None:
        return
    st.session_state.hero_limit = max(1, min(100, int(value)))


def _start_pipeline_job(keyword, subreddit, limit, run_start):
    job = {
        "lock": threading.Lock(),
        "cancel_event": threading.Event(),
        "stage": "scraping",
        "detail": "正在连接 Reddit...",
        "progress": 5,
        "done": False,
        "status": None,
        "message": "",
        "stats": {},
        "reddit_ids": [],
        "last_run": run_start,
        "keyword": keyword,
        "subreddit": subreddit,
    }

    def _progress(stage, detail):
        progress = {"scraping": 20, "filtering": 50, "analyzing": 75}.get(stage, 50)
        _job_set(job, stage=stage, detail=detail, progress=progress)

    def _worker():
        try:
            _job_set(
                job,
                stage="scraping",
                detail=f"搜索 r/{subreddit} · 「{keyword}」",
                progress=20,
            )

            stats = run_pipeline(
                keyword,
                subreddit,
                limit,
                progress_callback=_progress,
                cancel_check=job["cancel_event"].is_set,
                source="ui",
            )
            _job_set(job, reddit_ids=stats.get("reddit_ids", []))

            if stats.get("fetched", 0) == 0:
                _job_set(job, done=True, status="empty", stats=stats)
                return

            if stats.get("cancelled") or job["cancel_event"].is_set():
                _job_set(
                    job,
                    done=True,
                    status="cancelled",
                    message="已停止：不会继续消耗后续帖子的 AI 分析请求。",
                    stats=stats,
                )
                return

            _job_set(
                job,
                stage="analyzing",
                detail="深度分析完成 · 整理结果中",
                progress=95,
                done=True,
                status="ok",
                stats=stats,
            )
        except Exception as e:
            _job_set(job, done=True, status="error", message=str(e))

    job["thread"] = threading.Thread(target=_worker, daemon=True)
    job["thread"].start()
    return job


@st.fragment(run_every=1)
def _render_running_job(job):
    snapshot = _job_snapshot(job)

    if snapshot.get("done"):
        st.session_state.last_run = snapshot.get("last_run")
        st.session_state.last_run_ids = snapshot.get("reddit_ids", [])
        st.session_state.pipeline_result = {
            "status": snapshot.get("status"),
            "stats": snapshot.get("stats", {}),
            "message": snapshot.get("message", ""),
            "keyword": snapshot.get("keyword", ""),
            "subreddit": snapshot.get("subreddit", ""),
            "run_id": snapshot.get("stats", {}).get("run_id", ""),
        }
        st.session_state.pipeline_job = None
        st.session_state.ui_phase = "done"
        st.rerun()

    st.markdown(
        _render_loading(
            snapshot.get("stage", "scraping"),
            snapshot.get("detail", "正在处理..."),
            snapshot.get("progress", 5),
        ),
        unsafe_allow_html=True,
    )

    if snapshot.get("cancel_event") and snapshot["cancel_event"].is_set():
        st.warning("正在停止：当前已经发出的 API 请求可能会完成，但后续帖子不会继续分析。")
    else:
        cancel_left, cancel_mid, cancel_right = st.columns([1, 1, 1])
        with cancel_mid:
            if st.button("停止当前查询", type="secondary", use_container_width=True, key="cancel_run"):
                snapshot["cancel_event"].set()
                st.warning("已发送停止信号：会在当前这次请求结束后停止后续 AI 调用。")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    _inject_styles()
    default_subreddit = get_config_value("reddit.default_subreddit", "all")
    default_limit = get_int_config("reddit.default_limit", 30)

    # ── session state ──
    if "ui_phase" not in st.session_state:
        st.session_state.ui_phase = "idle"
    if "pipeline_result" not in st.session_state:
        st.session_state.pipeline_result = None

    # ── IDLE: Centered Hero Search ──────────────────────────────────────
    if st.session_state.ui_phase == "idle":

        # Spacer to push content toward center
        st.markdown("<div class='hero-spacer-top'></div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='hero-title'><span>Reddit 需求雷达</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='hero-subtitle'><span>"
            "从 Reddit 挖掘用户痛点，发现项目机会"
            "</span></div>",
            unsafe_allow_html=True,
        )

        col_l, col_c, col_r = st.columns([0.85, 1, 0.85])
        with col_c:
            keyword = st.text_input(
                "搜索关键词", value="",
                placeholder="例如：frustrated with / tired of / need a tool",
                autocomplete="off",
                key="hero_keyword",
            )
            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
            col_a, col_b = st.columns([1, 1])
            with col_a:
                subreddit = st.text_input(
                    "Subreddit 板块", value="",
                    placeholder="例如：all / SideProject / SaaS / Freelance",
                    autocomplete="off",
                    key="hero_subreddit",
                )
            with col_b:
                st.markdown(
                    "<div class='field-label'>搜索数量 "
                    "<span class='field-label-note'>（1-100）</span></div>",
                    unsafe_allow_html=True,
                )
                limit = st.number_input(
                    "搜索数量",
                    min_value=None,
                    max_value=None,
                    value=None,
                    step=1,
                    placeholder="输入 1-100",
                    label_visibility="collapsed",
                    on_change=_clamp_search_limit,
                    key="hero_limit",
                )

            st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

            go = st.button(
                "开始分析",
                type="primary",
                use_container_width=True,
                key="hero_go",
                disabled=not keyword.strip() or limit is None,
            )

        st.markdown("<div style='height: 22vh;'></div>", unsafe_allow_html=True)

        if go:
            st.session_state.ui_phase = "running"
            st.session_state.hero_keyword_val = keyword
            st.session_state.hero_subreddit_val = subreddit.strip() or "all"
            st.session_state.hero_limit_val = max(1, min(100, int(limit)))
            st.session_state.pipeline_job = None
            st.rerun()

    # ── RUNNING + RESULTS ────────────────────────────────────────────────
    else:
        keyword = st.session_state.get("hero_keyword_val", "")
        subreddit = st.session_state.get("hero_subreddit_val", default_subreddit)
        limit = st.session_state.get("hero_limit_val", default_limit)

        # ── RUNNING phase ──
        if st.session_state.ui_phase == "running":
            job = st.session_state.get("pipeline_job")
            if job is None:
                run_start = datetime.datetime.now(timezone.utc).isoformat()
                job = _start_pipeline_job(keyword, subreddit, limit, run_start)
                st.session_state.pipeline_job = job

            _render_running_job(job)

        # ── DONE phase: show results ──
        elif st.session_state.ui_phase == "done":
            result = st.session_state.pipeline_result
            last_run_ids = st.session_state.get("last_run_ids")

            # ── Filter bar ──
            with st.container():
                f1, f2, f3, f4 = st.columns([1.4, 1.2, 1.2, 0.6])
                with f1:
                    min_score = st.slider("最低分数", 0, 10, 0, 1, key="filter_score")
                with f2:
                    max_diff = st.slider("最高难度", 1, 5, 5, 1, key="filter_diff")
                with f3:
                    sort_by = st.selectbox("排序", ["priority", "score", "difficulty"],
                                           format_func=lambda x: {"priority": "优先级", "score": "分数", "difficulty": "难度"}[x],
                                           key="filter_sort")

            st.markdown("<hr style='margin:4px 0 12px;'>", unsafe_allow_html=True)

            # ── Error ──
            if result and result["status"] == "error":
                st.error(f"管线执行出错：{result['message']}")
                back_left, back_mid, back_right = st.columns([1, 1, 1])
                with back_mid:
                    if st.button("← 返回搜索", key="back_err", use_container_width=True):
                        st.session_state.ui_phase = "idle"
                        st.session_state.pipeline_result = None
                        st.rerun()

            # ── Empty ──
            elif result and result["status"] == "empty":
                st.warning(f"r/{result['subreddit']} 中未找到「**{result['keyword']}**」相关帖子。")
                st.markdown("""
                **建议**：换更宽泛的关键词 · 子版块改成 `all` · 等 1-2 分钟再试（可能被限流）
                """)
                back_left, back_mid, back_right = st.columns([1, 1, 1])
                with back_mid:
                    if st.button("← 返回搜索", key="back_empty", use_container_width=True):
                        st.session_state.ui_phase = "idle"
                        st.session_state.pipeline_result = None
                        st.rerun()

            elif result and result["status"] in {"ok", "cancelled"}:
                if result["status"] == "cancelled":
                    st.warning(result.get("message") or "已停止当前查询。已完成的部分会保留，未开始的 AI 请求不会继续执行。")

                last_run = st.session_state.get("last_run")
                posts = load_analyzed_posts(
                    min_score, max_diff,
                    sort_by=sort_by, since=last_run,
                    reddit_ids=last_run_ids,
                )

                if not posts:
                    notice_level, notice_message = _empty_result_notice(
                        result.get("stats", {}) if result else {}
                    )
                    if notice_level == "error":
                        st.error(notice_message)
                    else:
                        st.info(notice_message)
                    back_left, back_mid, back_right = st.columns([1, 1, 1])
                    with back_mid:
                        if st.button("← 返回搜索", key="back_nonew", use_container_width=True):
                            st.session_state.ui_phase = "idle"
                            st.session_state.pipeline_result = None
                            st.rerun()
                    return

                # ── Stats ──
                stats = get_stats(min_score, max_diff,
                                  since=last_run,
                                  reddit_ids=last_run_ids)
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("分析帖子", stats["total"])
                col2.metric("平均分数", f"{stats['avg_score']:.1f}")
                col3.metric("高优先级", stats["high_priority"])
                col4.metric("适合开源", stats["os_count"])

                # ── Export ──
                report_md = generate_report(posts, keyword, subreddit)
                now_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                st.download_button(
                    "↓ 导出 Markdown 报告",
                    data=report_md,
                    file_name=f"reddit-demand-report-{now_str}.md",
                    mime="text/markdown",
                )

                summary_keyword = _escape_html(keyword, "未填写")
                summary_subreddit = _escape_html(subreddit or "all", "all")
                st.markdown(
                    "<div class='result-summary'>"
                    "本次搜索：关键词 <strong>「{keyword}」</strong>"
                    "<span class='muted'>·</span>"
                    "板块 <strong>r/{subreddit}</strong>"
                    "<span class='muted'>·</span>"
                    "当前分析结果 <strong>{total}</strong> 个帖子"
                    "</div>".format(
                        keyword=summary_keyword,
                        subreddit=summary_subreddit,
                        total=stats["total"],
                    ),
                    unsafe_allow_html=True,
                )

                st.markdown("<hr>", unsafe_allow_html=True)

                # ── Forum-style post list ──
                st.markdown(
                    "<div style='font-family:Newsreader,serif;font-size:18px;font-weight:500;"
                    "color:#1a1a1a;margin-bottom:12px;'>分析结果</div>",
                    unsafe_allow_html=True,
                )

                for i, post in enumerate(posts):
                    score_val = _safe_float(post.get("filter_score"), 0.0)
                    diff_val = _clamp_int(post.get("difficulty"), 0, 5, 0)
                    monetize_val = post.get("monetize_potential")
                    monetize_stars = _plain_stars(_rating_from_level(monetize_val))
                    beginner_raw = post.get("beginner_difficulty")
                    beginner_val = _clamp_int(beginner_raw, 0, 5, 0)
                    beginner_stars = _plain_stars(beginner_val) if beginner_raw not in (None, "") else "暂无数据"
                    free_build_label = _escape_html(_free_build_label(post.get("free_build_possible")))
                    label = _escape_html(
                        _text(post.get("pain_point") or post.get("one_line_summary"), "（无标题）")[:90],
                        "（无标题）",
                    )
                    stars_filled = "★" * diff_val
                    stars_empty = "☆" * (5 - diff_val)
                    stars = f"{stars_filled}{stars_empty}"

                    pain = _escape_html(post.get("pain_point"))
                    quote = _escape_html(post.get("user_quote"))
                    audience = _escape_html(post.get("target_audience"))
                    idea = _escape_html(post.get("project_idea"))
                    os_val = _escape_html(post.get("opensource_value"))
                    os_reason = _escape_html(post.get("opensource_reason"), "")
                    m_val = _escape_html(post.get("monetize_potential"))
                    m_reason = _escape_html(post.get("monetize_reason"), "")
                    beginner_reason = _escape_html(post.get("beginner_reason"), "")
                    url = _safe_external_url(post.get("url"))
                    sub = _escape_html(post.get("subreddit"))
                    conf = _escape_html(post.get("confidence"), "")

                    os_reason_html = f'<div class="detail-reason">{os_reason}</div>' if os_reason else ""
                    m_reason_html = f'<div class="detail-reason">{m_reason}</div>' if m_reason else ""
                    beginner_reason_html = (
                        f'<div class="detail-reason">{beginner_reason}</div>'
                        if beginner_reason
                        else ""
                    )
                    url_html = f'<a href="{url}" target="_blank" class="detail-link">查看 Reddit 原帖</a>' if url else ""
                    conf_html = f'<div class="detail-conf">置信度：{conf}</div>' if conf else ""

                    st.markdown(f"""
                    <details class="post-card">
                      <summary class="post-title">
                        <span class="title-meta-inline">变现 {monetize_stars} · 难度 {stars} · 评分 {score_val:.1f}</span>
                        <span class="title-text-inline">{label}</span>
                      </summary>
                      <div class="post-meta">
                        评分 {score_val:.1f} &nbsp;·&nbsp; 难度 {stars_filled}{stars_empty} &nbsp;·&nbsp; 变现 {monetize_stars} &nbsp;·&nbsp; r/{sub}
                      </div>
                      <div class="post-body">
                        <div class="post-col">
                          <div class="detail-label">痛点</div>
                          <div class="detail-text">{pain}</div>
                          <div class="detail-label">用户原话</div>
                          <div class="detail-quote">> {quote}</div>
                          <div class="detail-label">目标用户</div>
                          <div class="detail-text">{audience}</div>
                        </div>
                        <div class="post-col">
                          <div class="detail-label">项目建议</div>
                          <div class="detail-text">{idea}</div>
                          <div class="detail-label">开源价值 — {os_val}</div>
                          {os_reason_html}
                          <div class="detail-label">变现潜力 — {m_val}</div>
                          {m_reason_html}
                          <div class="detail-label">AI 编程新手难度 — {beginner_stars}</div>
                          <div class="detail-text">{free_build_label}</div>
                          {beginner_reason_html}
                        </div>
                      </div>
                      {url_html}
                      {conf_html}
                    </details>
                    <div style="height:1px;background:#e8e5df;margin:4px 0;"></div>
                    """, unsafe_allow_html=True)

                # ── Back button ──
                st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
                back_left, back_mid, back_right = st.columns([1, 1, 1])
                with back_mid:
                    if st.button("← 新搜索", key="back_new", use_container_width=True):
                        st.session_state.ui_phase = "idle"
                        st.session_state.pipeline_result = None
                        st.session_state.pipeline_job = None
                        st.rerun()

            return


if __name__ == "__main__":
    main()
