# Reddit 需求雷达 — 分析报告

**生成时间**：{{ report_time }}

**搜索关键词**：`{{ keyword | md_cell }}`
**目标子版块**：r/{{ subreddit | md_cell }}
**数据来源**：Reddit 公开 JSON API
**分析引擎**：DeepSeek 两阶段分析

---

## 📊 概览

| 指标 | 数值 |
|---|---|
| 分析帖子数 | {{ total_analyzed }} |
| 发现痛点数 | {{ pain_count }} |
| 高优先级项目数 | {{ high_priority_count }} |
| 适合开源项目数 | {{ os_count }} |
| 平均痛点分数 | {{ avg_score }} |

---

## 🔥 高优先级项目机会

难度 ≤ 3 且评分 ≥ 7 的项目。

{% if high_priority_posts %}
| # | 痛点 | 项目建议 | 难度 | 评分 |
|---|---|---|---|---|
{% for p in high_priority_posts %}
| {{ loop.index }} | {{ p.pain_point | md_cell }} | {{ p.project_idea | md_cell }} | {{ p.difficulty | difficulty_label }}/5 | {{ (p.filter_score | safe_float) | round(1) }} |
{% endfor %}
{% else %}
*本次分析未发现高优先级项目。*
{% endif %}

---

## 📋 完整痛点清单

{% if posts %}
{% for p in posts %}
### {{ loop.index }}. {{ (p.pain_point or p.one_line_summary or '（无标题）') | md_cell }}

| 字段 | 内容 |
|---|---|
| **痛点** | {{ p.pain_point | md_cell }} |
| **用户原话** | {{ p.user_quote | md_cell }} |
| **目标用户** | {{ p.target_audience | md_cell }} |
| **项目建议** | {{ p.project_idea | md_cell }} |
| **难度** | {{ p.difficulty | difficulty_label }}/5 |
| **开源价值** | {{ p.opensource_value | md_cell }} |
| **变现潜力** | {{ p.monetize_potential | md_cell }} |
| **AI 编程新手难度** | {{ p.beginner_difficulty | difficulty_label }}/5 |
| **能否免费实现** | {{ p.free_build_possible | free_label | md_cell }} |
| **痛点评分** | {{ (p.filter_score | safe_float) | round(1) }} |
| **置信度** | {{ p.confidence | md_cell }} |
| **Reddit 原帖** | {{ p.url | md_link(p.subreddit or 'Reddit') }} |
| **帖子标题** | {{ p.title | md_cell }} |

{% if p.opensource_reason %}*开源理由：{{ p.opensource_reason | md_cell }}*{% endif %}
{% if p.monetize_reason %}*变现理由：{{ p.monetize_reason | md_cell }}*{% endif %}
{% if p.beginner_reason %}*新手说明：{{ p.beginner_reason | md_cell }}*{% endif %}

---
{% endfor %}
{% else %}
*无已分析的帖子。*
{% endif %}

---

*报告由 Reddit Demand Radar v0.1.0 自动生成*
