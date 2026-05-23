"""
AI 分析模块：两阶段 DeepSeek 分析管线。
- 第一阶段：过滤评分（filter_post）
- 第二阶段：深度洞察（analyze_post）
- 管线编排：run_analysis() 处理数据库中未分析的帖子
"""
import json
import math
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI
from settings import get_config_value, get_float_config

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

MAX_RETRIES = 3
RETRY_DELAY = 2


def _float_env_or_config(env_name, config_path, default):
    raw = os.getenv(env_name)
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            return default
    return get_float_config(config_path, default)


PROMPTS_DIR = os.path.join(_SCRIPT_DIR, "prompts")


def get_ai_model():
    return os.getenv("DEEPSEEK_MODEL") or get_config_value("ai.model", "deepseek-chat")


def get_ai_base_url():
    return os.getenv("DEEPSEEK_BASE_URL") or get_config_value(
        "ai.base_url",
        "https://api.deepseek.com",
    )


def get_filter_threshold():
    return _float_env_or_config("FILTER_THRESHOLD", "ai.filter_threshold", 5.0)


def create_ai_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "缺少 DEEPSEEK_API_KEY，请在 .env 中设置后重试。"
        )
    return OpenAI(api_key=api_key, base_url=get_ai_base_url())


def _render_prompt(template_path, variables):
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", str(value or ""))
    return text


def call_deepseek(
    client,
    system_prompt,
    user_prompt,
    model=None,
    source_run_id=None,
    reddit_id=None,
    stage=None,
):
    from db.database import finish_ai_call, start_ai_call

    model = model or get_ai_model()
    prompt_chars = len(system_prompt or "") + len(user_prompt or "")
    started = time.monotonic()
    call_id = start_ai_call(source_run_id, reddit_id, stage, model, prompt_chars)
    last_error = None
    attempt_count = 0
    for attempt in range(MAX_RETRIES):
        attempt_count = attempt + 1
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                timeout=60,
            )
            content = resp.choices[0].message.content
            finish_ai_call(
                call_id,
                status="success",
                attempt_count=attempt_count,
                response_text=content,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            return content
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    finish_ai_call(
        call_id,
        status="failed",
        attempt_count=attempt_count,
        error_message=last_error,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    raise RuntimeError(f"DeepSeek API 调用失败（重试 {MAX_RETRIES} 次）: {last_error}") from last_error


def parse_json_response(text):
    if not text:
        raise ValueError("AI 返回为空")
    text = text.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


def _coerce_float(value, field, minimum=None, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} 必须是数字") from e
    if not math.isfinite(parsed):
        raise ValueError(f"{field} 必须是有限数字")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field} 不能小于 {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{field} 不能大于 {maximum}")
    return parsed


def _coerce_int(value, field, minimum=None, maximum=None):
    parsed = int(round(_coerce_float(value, field, minimum, maximum)))
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field} 不能小于 {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{field} 不能大于 {maximum}")
    return parsed


def _coerce_text(value, field, required=True):
    if value is None:
        if required:
            raise ValueError(f"{field} 不能为空")
        return ""
    text = str(value).strip()
    if required and not text:
        raise ValueError(f"{field} 不能为空")
    return text


def _enum_value(value, field, allowed, default=None):
    text = str(value or "").strip().lower()
    if text in allowed:
        return text
    if default is not None:
        return default
    raise ValueError(f"{field} 必须是 {', '.join(sorted(allowed))} 之一")


def validate_filter_result(result):
    return {
        "pain_clarity": _coerce_int(result.get("pain_clarity"), "pain_clarity", 0, 10),
        "frequency": _coerce_int(result.get("frequency"), "frequency", 0, 10),
        "actionability": _coerce_int(result.get("actionability"), "actionability", 0, 10),
        "total": _coerce_float(result.get("total"), "total", 0, 10),
        "one_line_summary": _coerce_text(result.get("one_line_summary"), "one_line_summary"),
        "confidence": _enum_value(
            result.get("confidence"),
            "confidence",
            {"low", "medium", "high"},
            default="medium",
        ),
    }


def validate_insight_result(result):
    return {
        "pain_point": _coerce_text(result.get("pain_point"), "pain_point"),
        "user_quote": _coerce_text(result.get("user_quote"), "user_quote", required=False),
        "target_audience": _coerce_text(result.get("target_audience"), "target_audience"),
        "project_idea": _coerce_text(result.get("project_idea"), "project_idea"),
        "difficulty": _coerce_int(result.get("difficulty"), "difficulty", 1, 5),
        "opensource_value": _enum_value(
            result.get("opensource_value"),
            "opensource_value",
            {"low", "medium", "high"},
        ),
        "opensource_reason": _coerce_text(result.get("opensource_reason"), "opensource_reason"),
        "monetize_potential": _enum_value(
            result.get("monetize_potential"),
            "monetize_potential",
            {"low", "medium", "high"},
        ),
        "monetize_reason": _coerce_text(result.get("monetize_reason"), "monetize_reason"),
        "beginner_difficulty": _coerce_int(
            result.get("beginner_difficulty"),
            "beginner_difficulty",
            1,
            5,
        ),
        "free_build_possible": _enum_value(
            result.get("free_build_possible"),
            "free_build_possible",
            {"yes", "partial", "no"},
        ),
        "beginner_reason": _coerce_text(result.get("beginner_reason"), "beginner_reason"),
        "confidence": _enum_value(
            result.get("confidence"),
            "confidence",
            {"low", "medium", "high"},
            default="medium",
        ),
    }


def filter_post(client, post, source_run_id=None):
    system_prompt = "You are a user-needs analyst. Always respond with valid JSON only."
    user_prompt = _render_prompt(
        os.path.join(PROMPTS_DIR, "filter.txt"),
        {
            "title": post.get("title", ""),
            "body": post.get("body", ""),
            "subreddit": post.get("subreddit", ""),
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
        },
    )
    raw = call_deepseek(
        client,
        system_prompt,
        user_prompt,
        source_run_id=source_run_id,
        reddit_id=post.get("reddit_id"),
        stage="filter",
    )
    result = validate_filter_result(parse_json_response(raw))
    result["_raw"] = raw
    return result


def analyze_post(client, post, one_line_summary="", source_run_id=None):
    system_prompt = "You are a product analyst. Always respond with valid JSON only."
    user_prompt = _render_prompt(
        os.path.join(PROMPTS_DIR, "insight.txt"),
        {
            "title": post.get("title", ""),
            "body": post.get("body", ""),
            "subreddit": post.get("subreddit", ""),
            "one_line_summary": one_line_summary,
        },
    )
    raw = call_deepseek(
        client,
        system_prompt,
        user_prompt,
        source_run_id=source_run_id,
        reddit_id=post.get("reddit_id"),
        stage="insight",
    )
    result = validate_insight_result(parse_json_response(raw))
    result["_raw"] = raw
    return result


def _normalize_reddit_ids(reddit_ids):
    if reddit_ids is None:
        return None
    return list(dict.fromkeys(str(reddit_id) for reddit_id in reddit_ids if reddit_id))


def _cancel_requested(cancel_check):
    if cancel_check is None:
        return False
    return bool(cancel_check())


def _cancelled_stats(reddit_ids):
    stats = _count_stats(reddit_ids)
    stats["cancelled"] = True
    return stats


def run_analysis(
    limit=None,
    source_run_id=None,
    progress_callback=None,
    reddit_ids=None,
    cancel_check=None,
):
    """
    分析数据库中未处理的帖子。
    返回统计 dict：{'filtered': N, 'analyzed': N, 'filtered_out': N, 'failed': N}

    reddit_ids 可选：只分析指定帖子，用于一次抓取/一次 webhook 批次。
    progress_callback 可选，签名 callback(stage: str, detail: str)。
    cancel_check 可选，返回 True 时停止后续 AI 请求。
    stage: 'filtering' | 'analyzing'
    """
    from db.database import (
        get_unprocessed_posts,
        update_filter_score,
        mark_filtered_out,
        get_high_score_posts,
        update_full_analysis,
        mark_post_failed,
        record_analysis_result,
        update_run,
    )

    normalized_ids = _normalize_reddit_ids(reddit_ids)
    client = None
    filter_threshold = get_filter_threshold()

    if _cancel_requested(cancel_check):
        return _cancelled_stats(normalized_ids)

    # 第一阶段：过滤评分（只处理 status='new' 的帖子）
    new_posts = get_unprocessed_posts(limit=limit, reddit_ids=normalized_ids)

    if new_posts:
        client = create_ai_client()
        if progress_callback:
            progress_callback("filtering", f"第1阶段：过滤评分（{len(new_posts)} 条帖子）")
        print(f"\n第一阶段：过滤评分（{len(new_posts)} 条帖子）")
        for i, post in enumerate(new_posts, 1):
            if _cancel_requested(cancel_check):
                print("\n已请求停止：跳过剩余 AI 过滤评分。")
                return _cancelled_stats(normalized_ids)
            try:
                result = filter_post(client, post, source_run_id=source_run_id)
                score = result.get("total", 0)
                summary = result.get("one_line_summary", "")
                raw_json = json.dumps(result.get("_raw", result), ensure_ascii=False)
                update_filter_score(post["reddit_id"], score, summary, raw_json)
                record_analysis_result(
                    source_run_id,
                    post["reddit_id"],
                    "filter",
                    result,
                )
                if score < filter_threshold:
                    mark_filtered_out(post["reddit_id"])
                print(f"  [{i}/{len(new_posts)}] score={score:.1f}  {summary[:60]}")
            except Exception as e:
                mark_post_failed(post["reddit_id"], str(e)[:500])
                print(f"  [{i}/{len(new_posts)}] FAILED: {e}")

    if _cancel_requested(cancel_check):
        print("\n已请求停止：跳过深度分析。")
        return _cancelled_stats(normalized_ids)

    # 第二阶段：深度分析（只分析 filter_score >= threshold 的帖子）
    high_posts = get_high_score_posts(filter_threshold, reddit_ids=normalized_ids)
    if limit is not None and len(high_posts) > limit:
        high_posts = high_posts[:limit]

    if not high_posts:
        stats = _count_stats(normalized_ids)
        update_run(source_run_id, stats=stats)
        print(f"\n完成：filtered_out={stats['filtered_out']}, "
              f"analyzed={stats['analyzed']}, failed={stats['failed']}")
        return stats

    if client is None:
        client = create_ai_client()

    if progress_callback:
        progress_callback("analyzing", f"第2阶段：深度分析（{len(high_posts)} 条帖子）")
    print(f"\n第二阶段：深度分析（{len(high_posts)} 条帖子）")
    for i, post in enumerate(high_posts, 1):
        if _cancel_requested(cancel_check):
            print("\n已请求停止：跳过剩余深度分析。")
            return _cancelled_stats(normalized_ids)
        try:
            result = analyze_post(
                client, post,
                one_line_summary=post.get("one_line_summary", ""),
                source_run_id=source_run_id,
            )
            update_full_analysis(post["reddit_id"], result)
            record_analysis_result(
                source_run_id,
                post["reddit_id"],
                "insight",
                result,
            )
            idea = result.get("project_idea", "")[:60]
            print(f"  [{i}/{len(high_posts)}] difficulty={result.get('difficulty','?')}  {idea}")
        except Exception as e:
            mark_post_failed(post["reddit_id"], str(e)[:500])
            print(f"  [{i}/{len(high_posts)}] FAILED: {e}")

    stats = _count_stats(normalized_ids)
    update_run(source_run_id, stats=stats)
    print(f"\n完成：filtered_out={stats['filtered_out']}, "
          f"analyzed={stats['analyzed']}, failed={stats['failed']}")
    return stats


def _count_stats(reddit_ids=None):
    from db.database import get_connection
    normalized_ids = _normalize_reddit_ids(reddit_ids)
    if normalized_ids == []:
        return {"filtered_out": 0, "analyzed": 0, "failed": 0}

    conn = get_connection()
    params = []
    ids_clause = ""
    if normalized_ids is not None:
        placeholders = ",".join(["?"] * len(normalized_ids))
        ids_clause = f" AND reddit_id IN ({placeholders})"
        params.extend(normalized_ids)
    filtered_out = conn.execute(
        f"SELECT COUNT(*) FROM posts WHERE analysis_status='filtered_out'{ids_clause}",
        params,
    ).fetchone()[0]
    analyzed = conn.execute(
        f"SELECT COUNT(*) FROM posts WHERE analysis_status='analyzed'{ids_clause}",
        params,
    ).fetchone()[0]
    failed = conn.execute(
        f"SELECT COUNT(*) FROM posts WHERE analysis_status='failed'{ids_clause}",
        params,
    ).fetchone()[0]
    conn.close()
    return {"filtered_out": filtered_out, "analyzed": analyzed, "failed": failed}
