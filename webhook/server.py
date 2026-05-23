"""
FastAPI Webhook 端点 — 接收外部推送帖子并创建 run。
启动：uvicorn webhook.server:app --port 8000
"""
import hashlib
import hmac
import os
import sys
import time

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from db.database import add_run_post, create_run, init_db, insert_post, update_run
from settings import get_int_config

app = FastAPI(title="Reddit Demand Radar Webhook", version="0.1.0")


def _webhook_token() -> str:
    return (os.getenv("WEBHOOK_TOKEN") or "").strip()


def _max_posts_per_request() -> int:
    configured = get_int_config("webhook.max_posts_per_request", 25)
    return max(1, min(100, configured))


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix):].strip()
    return ""


def _verify_webhook_token(
    x_webhook_token: str | None,
    authorization: str | None,
) -> None:
    expected = _webhook_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Webhook 未配置 WEBHOOK_TOKEN，已拒绝请求以避免意外触发 AI 消耗。",
        )

    supplied = (x_webhook_token or "").strip() or _extract_bearer_token(authorization)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Webhook token 无效。")


class PostPayload(BaseModel):
    title: str
    body: Optional[str] = ""
    url: Optional[str] = ""
    subreddit: Optional[str] = ""
    score: Optional[int] = 0
    num_comments: Optional[int] = 0
    created_utc: Optional[float] = None
    reddit_id: Optional[str] = None


def _generate_reddit_id(post: PostPayload) -> str:
    if post.reddit_id:
        return post.reddit_id
    if post.url:
        return hashlib.sha256(post.url.encode()).hexdigest()[:16]
    source = f"{post.title}|{post.subreddit}|{post.created_utc or 0}"
    return hashlib.sha256(source.encode()).hexdigest()[:16]


@app.post("/webhook/posts")
def receive_posts(
    posts: List[PostPayload],
    x_webhook_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    _verify_webhook_token(x_webhook_token, authorization)

    if not posts:
        raise HTTPException(status_code=400, detail="Webhook 至少需要接收 1 条帖子。")

    max_posts = _max_posts_per_request()
    if len(posts) > max_posts:
        raise HTTPException(
            status_code=413,
            detail=f"单次 Webhook 最多接收 {max_posts} 条帖子，请减少 n8n 批量大小。",
        )

    init_db()

    received = len(posts)
    new_count = 0
    reddit_ids = []
    subreddits = sorted({(post.subreddit or "").strip() for post in posts if post.subreddit})
    run_id = create_run(
        source="webhook",
        subreddit=",".join(subreddits) if subreddits else "",
        limit_count=received,
        status="ingested",
        metadata={"received": received},
    )

    for post in posts:
        reddit_id = _generate_reddit_id(post)
        reddit_ids.append(reddit_id)
        add_run_post(run_id, reddit_id)
        inserted = insert_post({
            "reddit_id": reddit_id,
            "title": post.title,
            "body": post.body or "",
            "url": post.url or "",
            "subreddit": post.subreddit or "",
            "score": post.score or 0,
            "num_comments": post.num_comments or 0,
            "created_utc": post.created_utc or time.time(),
        })
        if inserted:
            new_count += 1

    stats = {
        "fetched": received,
        "new": new_count,
        "skipped": received - new_count,
        "filtered_out": 0,
        "analyzed": 0,
        "failed": 0,
    }
    update_run(run_id, status="ingested", stats=stats)

    return {
        "status": "ok",
        "run_id": run_id,
        "received": received,
        "new": new_count,
        "skipped": received - new_count,
        "analysis_status": "not_started",
        "message": "Webhook 已入库并创建 run；未自动调用 AI。需要分析时运行 python main.py --analyze-run <run_id>。",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
