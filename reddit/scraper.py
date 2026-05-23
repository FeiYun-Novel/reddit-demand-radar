"""
Reddit 帖子抓取模块。
使用 requests 直接访问 Reddit 公开 JSON API（无需 OAuth）。
数据库路径和 .env 加载均基于项目根目录计算。
"""

import os
import time
import requests
from urllib.parse import urlparse

from dotenv import load_dotenv
from settings import get_config_value

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

USER_AGENT = os.getenv("REDDIT_USER_AGENT", "reddit-demand-radar/0.1")
REDDIT_BASE = "https://www.reddit.com"
DEFAULT_SEARCH_SORT = get_config_value("reddit.search_sort", "relevance")
DEFAULT_SEARCH_TIME_FILTER = get_config_value("reddit.search_time_filter", "month")


def normalize_subreddit_name(subreddit_name):
    """Accept 'SideProject', 'r/SideProject', '/r/SideProject', Reddit URLs, or 'all'."""
    value = (subreddit_name or "all").strip()
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower().endswith("reddit.com"):
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0].lower() == "r":
            value = path_parts[1]

    lower_value = value.lower()
    if lower_value.startswith("/r/"):
        value = value[3:]
    elif lower_value.startswith("r/"):
        value = value[2:]
    value = value.strip("/")
    return value or "all"


def _retry_after_seconds(header_value, default=60):
    try:
        return max(1, int(header_value))
    except (TypeError, ValueError):
        return default


def create_reddit_client():
    """返回配置好的 requests Session，用于访问 Reddit 公开 JSON API。"""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def search_posts(session, keyword, subreddit_name, limit=50,
                 sort=None, time_filter=None):
    """
    搜索 Reddit 帖子，返回 list[dict]。

    每个 dict 包含：reddit_id, title, body, url, subreddit,
    score, num_comments, created_utc。
    """
    subreddit_name = normalize_subreddit_name(subreddit_name)
    sort = sort or DEFAULT_SEARCH_SORT
    time_filter = time_filter or DEFAULT_SEARCH_TIME_FILTER

    if subreddit_name and subreddit_name.lower() != "all":
        url = f"{REDDIT_BASE}/r/{subreddit_name}/search.json"
    else:
        url = f"{REDDIT_BASE}/search.json"

    params = {
        "q": keyword,
        "sort": sort,
        "t": time_filter,
        "limit": limit,
    }
    if subreddit_name and subreddit_name.lower() != "all":
        params["restrict_sr"] = "on"

    resp = session.get(url, params=params, timeout=30)

    if resp.status_code == 429:
        retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
        print(f"Reddit 限流，等待 {retry_after}s 后重试...")
        time.sleep(retry_after)
        resp = session.get(url, params=params, timeout=30)

    resp.raise_for_status()
    data = resp.json()

    posts = []
    for child in data.get("data", {}).get("children", []):
        if child.get("kind") != "t3":
            continue
        post_data = child["data"]
        posts.append({
            "reddit_id": post_data["id"],
            "title": post_data.get("title", ""),
            "body": post_data.get("selftext", ""),
            "url": f"{REDDIT_BASE}{post_data['permalink']}",
            "subreddit": post_data.get("subreddit", ""),
            "score": post_data.get("score", 0),
            "num_comments": post_data.get("num_comments", 0),
            "created_utc": post_data.get("created_utc", 0),
        })

    return posts


def scrape_and_save(session, keyword, subreddit_name, limit):
    """抓取 Reddit 帖子并写入数据库，返回统计 dict。"""
    from db.database import init_db, insert_post

    init_db()
    subreddit_name = normalize_subreddit_name(subreddit_name)

    try:
        posts = search_posts(session, keyword, subreddit_name, limit)
    except requests.exceptions.HTTPError as e:
        resp = e.response if hasattr(e, "response") else None
        status = resp.status_code if resp is not None else "?"
        raise RuntimeError(
            f"Reddit API 返回 {status}：请检查搜索参数或稍后重试。"
        ) from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Reddit 请求失败：{e}。请检查网络连接。"
        ) from e

    if not posts:
        return {
            "keyword": keyword,
            "subreddit": subreddit_name,
            "fetched": 0,
            "new": 0,
            "skipped": 0,
            "reddit_ids": [],
        }

    new = 0
    skipped = 0
    for post in posts:
        inserted = insert_post(post)
        if inserted:
            new += 1
        else:
            skipped += 1

    return {
        "keyword": keyword,
        "subreddit": subreddit_name,
        "fetched": len(posts),
        "new": new,
        "skipped": skipped,
        "reddit_ids": [post["reddit_id"] for post in posts],
    }
