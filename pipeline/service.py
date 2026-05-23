"""
Shared Reddit scrape + AI analysis pipeline.

CLI, Streamlit, and Webhook entrypoints should call this module instead of
rebuilding the same orchestration in each surface.
"""
from __future__ import annotations

from typing import Callable

from ai.analyzer import run_analysis
from db.database import (
    add_run_posts,
    create_run,
    get_run_reddit_ids,
    init_db,
    update_run,
)
from reddit.scraper import create_reddit_client, scrape_and_save

ProgressCallback = Callable[[str, str], None]
CancelCheck = Callable[[], bool]


def clamp_limit(limit, minimum=1, maximum=100, default=30):
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _cancel_requested(cancel_check: CancelCheck | None) -> bool:
    return bool(cancel_check and cancel_check())


def run_pipeline(
    keyword,
    subreddit,
    limit,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
    source="cli",
    run_id=None,
):
    """Run one scrape + analysis batch and return merged stats.

    The returned dict always includes scrape stats and, when available,
    analysis stats. If cancellation is requested after scraping, the batch
    returns with ``cancelled=True`` before starting any AI calls.
    """
    limit = clamp_limit(limit)
    init_db()
    run_id = run_id or create_run(
        source=source,
        keyword=keyword,
        subreddit=subreddit,
        limit_count=limit,
        status="created",
    )
    update_run(run_id, status="scraping")
    if progress_callback:
        progress_callback("scraping", f"搜索关键词 '{keyword}' r/{subreddit}...")

    session = create_reddit_client()
    scrape_stats = scrape_and_save(session, keyword, subreddit, limit)
    reddit_ids = scrape_stats.get("reddit_ids", [])
    add_run_posts(run_id, reddit_ids)
    update_run(run_id, status="scraped", stats=scrape_stats)

    if _cancel_requested(cancel_check):
        update_run(run_id, status="cancelled", stats=scrape_stats)
        return {
            **scrape_stats,
            "run_id": run_id,
            "filtered_out": 0,
            "analyzed": 0,
            "failed": 0,
            "cancelled": True,
        }

    if not reddit_ids:
        stats = {**scrape_stats, "run_id": run_id, "filtered_out": 0, "analyzed": 0, "failed": 0}
        update_run(run_id, status="completed", stats=stats)
        return stats

    update_run(run_id, status="analyzing")

    analysis_stats = run_analysis(
        progress_callback=progress_callback,
        reddit_ids=reddit_ids,
        cancel_check=cancel_check,
        source_run_id=run_id,
    )
    stats = {**scrape_stats, **analysis_stats, "run_id": run_id}
    update_run(
        run_id,
        status="cancelled" if analysis_stats.get("cancelled") else "completed",
        stats=stats,
    )
    return stats


def run_analysis_for_run(
    run_id,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
):
    init_db()
    reddit_ids = get_run_reddit_ids(run_id)
    update_run(run_id, status="analyzing")
    stats = run_analysis(
        progress_callback=progress_callback,
        reddit_ids=reddit_ids,
        cancel_check=cancel_check,
        source_run_id=run_id,
    )
    stats["run_id"] = run_id
    update_run(
        run_id,
        status="cancelled" if stats.get("cancelled") else "completed",
        stats=stats,
    )
    return stats


def run_analysis_only(
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
):
    init_db()
    run_id = create_run(source="cli_analyze_only", status="analyzing")
    stats = run_analysis(
        progress_callback=progress_callback,
        cancel_check=cancel_check,
        source_run_id=run_id,
    )
    stats["run_id"] = run_id
    update_run(
        run_id,
        status="cancelled" if stats.get("cancelled") else "completed",
        stats=stats,
    )
    return stats
