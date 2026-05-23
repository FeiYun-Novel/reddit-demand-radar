"""
Reddit Demand Radar — 命令行入口。
用法：
  python main.py --keyword "need a tool" [--subreddit SideProject] [--limit 30]
  python main.py --analyze-only
"""
import argparse
import os

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from pipeline.service import (
    clamp_limit,
    run_analysis_for_run,
    run_analysis_only,
    run_pipeline,
)
from settings import get_config_value, get_int_config


def main():
    default_subreddit = get_config_value("reddit.default_subreddit", "all")
    default_limit = clamp_limit(get_int_config("reddit.default_limit", 30))

    parser = argparse.ArgumentParser(
        description="Reddit Demand Radar — 挖掘 Reddit 痛点信号",
    )
    parser.add_argument(
        "--keyword", default="",
        help="搜索关键词，例如 'need a tool'",
    )
    parser.add_argument(
        "--subreddit", default=default_subreddit,
        help=f"限定子版块，默认 '{default_subreddit}'",
    )
    parser.add_argument(
        "--limit", type=int, default=default_limit,
        help=f"抓取帖子数量上限，范围 1-100，默认 {default_limit}",
    )
    parser.add_argument(
        "--analyze-only", action="store_true",
        help="只分析数据库中未处理的帖子，不抓取新数据",
    )
    parser.add_argument(
        "--analyze-run", default="",
        help="只分析某次 Webhook / 抓取 run_id 下的帖子",
    )
    args = parser.parse_args()

    if args.analyze_run:
        stats = run_analysis_for_run(args.analyze_run)
        print()
        print("=" * 50)
        print("  指定 Run 分析完成")
        print("=" * 50)
        print(f"  Run ID    : {stats.get('run_id', args.analyze_run)}")
        print(f"  过滤滤除  : {stats.get('filtered_out', 0)}")
        print(f"  深度分析  : {stats.get('analyzed', 0)}")
        print(f"  失败      : {stats.get('failed', 0)}")
        print("=" * 50)
        return

    if args.analyze_only:
        stats = run_analysis_only()
        print()
        print("=" * 50)
        print("  分析完成")
        print("=" * 50)
        print(f"  Run ID    : {stats.get('run_id', '')}")
        print(f"  过滤滤除  : {stats.get('filtered_out', 0)}")
        print(f"  深度分析  : {stats.get('analyzed', 0)}")
        print(f"  失败      : {stats.get('failed', 0)}")
        print("=" * 50)
        return

    if not args.keyword:
        parser.error("需要提供 --keyword 参数，或使用 --analyze-only")

    stats = run_pipeline(
        args.keyword,
        args.subreddit,
        clamp_limit(args.limit),
        source="cli",
    )

    print()
    print("=" * 50)
    print("  管线完成")
    print("=" * 50)
    print(f"  关键词    : {stats['keyword']}")
    print(f"  子版块    : {stats['subreddit']}")
    print(f"  Run ID    : {stats.get('run_id', '')}")
    print(f"  获取帖子  : {stats['fetched']}")
    print(f"  新入库    : {stats['new']}")
    print(f"  已存在    : {stats['skipped']}")
    print(f"  过滤滤除  : {stats.get('filtered_out', 0)}")
    print(f"  深度分析  : {stats.get('analyzed', 0)}")
    print(f"  失败      : {stats.get('failed', 0)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
