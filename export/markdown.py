"""
报告生成 — 使用 Jinja2 模板将分析结果渲染为 Markdown 报告。
"""
import datetime
import math
import os
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))


def _markdown_cell(value, fallback="-"):
    if value is None or value == "":
        return fallback
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(part.strip() for part in text.split("\n") if part.strip())
    text = text.replace("|", r"\|")
    return text or fallback


def _markdown_link(url, label="Reddit 原帖"):
    if not url:
        return "-"
    raw_url = " ".join(str(url).strip().split())
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _markdown_cell(raw_url)
    safe_url = raw_url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    safe_label = _markdown_cell(label).replace("[", r"\[").replace("]", r"\]")
    return f"[{safe_label}]({safe_url})"


def _safe_float(value, default=0.0):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _safe_int(value, default=5):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return int(parsed) if math.isfinite(parsed) else default


def _difficulty_label(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(parsed) or parsed < 1 or parsed > 5:
        return "-"
    return str(int(parsed))


def _free_build_label(value):
    normalized = str(value or "").strip().lower()
    mapping = {
        "yes": "基本可免费实现",
        "partial": "部分可免费实现",
        "no": "较难免费实现",
    }
    return mapping.get(normalized, value or "-")


_env.filters["md_cell"] = _markdown_cell
_env.filters["md_link"] = _markdown_link
_env.filters["safe_float"] = _safe_float
_env.filters["difficulty_label"] = _difficulty_label
_env.filters["free_label"] = _free_build_label


def generate_report(posts, keyword, subreddit):
    """根据分析结果生成 Markdown 报告文本。"""
    total_analyzed = len(posts)
    high_priority_posts = [
        p
        for p in posts
        if _safe_int(p.get("difficulty"), 5) <= 3
        and _safe_float(p.get("filter_score"), 0.0) >= 7
    ]
    pain_count = sum(1 for p in posts if p.get("pain_point"))

    scores = [_safe_float(p.get("filter_score"), 0.0) for p in posts]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    os_count = sum(1 for p in posts if p.get("opensource_value") == "high")

    template = _env.get_template("template.md")
    return template.render(
        report_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        keyword=keyword or "（无）",
        subreddit=subreddit or "all",
        total_analyzed=total_analyzed,
        pain_count=pain_count,
        high_priority_count=len(high_priority_posts),
        os_count=os_count,
        avg_score=avg_score,
        high_priority_posts=high_priority_posts,
        posts=posts,
    )
