# Reddit Demand Radar 📡

**Reddit 需求雷达** — 从 Reddit 帖子中挖掘用户痛点，用 AI 分析项目机会。

*Mine user pain points from Reddit, analyze project opportunities with AI.*

[![License: Non-Commercial](https://img.shields.io/badge/license-non--commercial-orange.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
![Version](https://img.shields.io/badge/version-0.1.0-lightgrey)

---

## 这是什么？ / What is this?

输入一个关键词，Reddit 需求雷达会：

1. 搜索 Reddit 相关帖子
2. 用 AI 过滤出真正包含用户痛点的帖子
3. 对高价值帖子做深度分析，生成项目建议
4. 在 Streamlit 面板中展示结果，支持筛选和排序
5. 导出 Markdown 报告

*Input a keyword, and Reddit Demand Radar will search Reddit, filter posts for real user pain points, perform deep AI analysis to generate project ideas, and display results in a Streamlit dashboard with filtering, sorting, and Markdown export.*

## 快速开始 / Quick Start

### 1. 克隆项目

```bash
git clone <repo-url>
cd reddit-demand-radar
```

### 2. 配置环境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，填入 DeepSeek API Key：

```bash
DEEPSEEK_API_KEY=<your-deepseek-api-key>
REDDIT_USER_AGENT=reddit-demand-radar/0.1
```

> Reddit 公开 JSON API 无需 OAuth，开箱即用。

### 3. 命令行抓取 + 分析

```bash
python main.py --keyword "need a tool" --subreddit SideProject --limit 10
```

### 4. 启动 Streamlit 面板

```bash
streamlit run ui/app.py --server.address 127.0.0.1 --server.port 8502
```

打开浏览器访问 `http://127.0.0.1:8502`，输入关键词即可开始。

> 说明：`127.0.0.1:8502` 只是本机网页地址，不能自己启动 Streamlit。只有当上面的 Streamlit 服务已经在运行时，复制这个地址到浏览器才会打开页面。

### 5. （可选）启动 Webhook 服务

Webhook 默认有成本保护：必须在 `.env` 中配置 `WEBHOOK_TOKEN`，并在请求 header 里带上同一个 token。

```bash
uvicorn webhook.server:app --port 8000
```

默认情况下，Webhook 只负责接收并写入帖子，不会立刻调用 AI。返回结果里会包含一个 `run_id`，需要分析这批帖子时运行：

```bash
python main.py --analyze-run <run_id>
```

参见 [n8n 配置指南](docs/n8n-setup.md)。

## 两阶段 AI 分析 / Two-Stage AI Analysis

| 阶段 | 目的 | 输出 |
|---|---|---|
| **过滤评分** | 判断帖子是否包含真实用户痛点 | `filter_score` + 一句话概括 |
| **深度分析** | 将高价值帖子转为项目机会 | 痛点/项目建议/难度/开源价值/变现潜力/新手可做性 |

评分阈值可在 [config.yaml](config.yaml) 中调整：

```yaml
ai:
  filter_threshold: 5.0
```

低于此阈值的帖子被标记为 `filtered_out`，不消耗深度分析 API。

在网页面板中点击“停止当前查询”可以停止后续帖子继续 AI 分析。已经发出的单次 API 请求通常无法撤回，但停止后不会继续处理后面的帖子，用来减少误点或关键词输错时的额外消耗。

分析结果标题会按 `变现星级 · 难度星级 · 痛点评分 · 标题` 展示，展开后仍保留完整的评分、难度、变现理由和 AI 编程新手评估。

## 项目结构 / Project Structure

```text
reddit-demand-radar/
  main.py               # CLI 入口
  config.yaml           # 配置文件
  settings.py           # 读取 config.yaml 的配置层
  requirements.txt      # Python 依赖
  reddit/scraper.py     # Reddit 抓取（公开 JSON API）
  ai/analyzer.py        # AI 分析管线
  ai/prompts/           # filter + insight Prompt 模板
  db/database.py        # SQLite 建表与 CRUD
  ui/app.py             # Streamlit 可视化面板
  export/markdown.py    # Markdown 报告生成
  export/template.md    # 报告模板
  webhook/server.py     # FastAPI Webhook 端点
  pipeline/service.py   # CLI / UI / Webhook 共享业务管线
  docs/                 # 文档目录
```

## n8n 自动化 / n8n Integration

支持通过 n8n 定时触发 Reddit 搜索，自动推送到本地 Webhook 入库：

```
Schedule Trigger → Reddit API Search → Code (格式化) → POST Webhook
```

详细配置见 [docs/n8n-setup.md](docs/n8n-setup.md)。

## 技术栈 / Tech Stack

- **Python 3.10+**
- **Reddit 公开 JSON API**（requests）— 无需 OAuth
- **DeepSeek**（OpenAI 兼容 SDK）— 两阶段分析
- **SQLite** — 本地持久化
- **Streamlit** — 可视化面板
- **FastAPI + Uvicorn** — Webhook 端点
- **Jinja2** — 报告模板

## 参考与署名 / Attribution

This project is an AI-assisted educational rewrite inspired by [Mohamedsaleh14/Reddit_Scrapper](https://github.com/Mohamedsaleh14/Reddit_Scrapper). Credit to Mohamed-Saleh and Cronlytic.com. See [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md).

## 安全 / Security

- `.env` 和 `data/` 目录已在 `.gitignore` 中，不会提交到 Git
- Reddit 使用公开 JSON API，无需配置 OAuth 凭证
- 所有数据存储在本地 SQLite，不上传云端
- Webhook 默认需要 `WEBHOOK_TOKEN`，并且默认不自动触发 AI 分析，避免后台自动化意外消耗 API 额度
- 每次 CLI / UI / Webhook 批次会记录 `run_id`，AI 调用会写入本地 `ai_calls` 账本，分析结果历史会写入 `analysis_results`，便于排查成本和失败原因

本仓库只包含代码、模板和公开文档，不包含本地 `.env`、SQLite 数据库、抓取结果或内部开发笔记。

## 许可与商用限制 / License & Commercial Use

本项目仅用于个人学习、研究和非商用参考。由于项目思路和实现参考了非商用授权的相关项目，未经项目维护者和相关上游权利方明确许可，**不得商用**。

This project is for personal learning, research, and non-commercial reference use only. Some ideas or implementation patterns are inspired by non-commercial upstream work, so commercial use is not allowed unless you obtain explicit permission from the maintainers and relevant upstream rights holders.

## 常见问题 / FAQ

**Q: 需要 Reddit API Key 吗？**
不需要。使用 Reddit 公开 JSON API（`reddit.com/search.json`），无需注册应用。

**Q: 必须用 DeepSeek 吗？**
目前默认使用 DeepSeek。如果想换其他模型，在 `.env` 中修改 `DEEPSEEK_API_KEY` 和 [config.yaml](config.yaml) 中的 `ai.base_url` / `ai.model` 即可（支持任意 OpenAI 兼容 API）。

**Q: 抓不到帖子？**
Reddit 公开 API 有频率限制（约 60 次/分钟），如果连续请求可能暂时被限制。建议搜索间隔 > 1 秒。

**Q: AI 分析失败？**
检查 `.env` 中的 `DEEPSEEK_API_KEY` 是否正确，以及 DeepSeek 账户余额是否充足。

**Q: 分析一次多少钱？**
费用取决于模型价格、帖子数量、正文长度和过滤阈值。低于阈值的帖子只会经过第一阶段过滤，不会进入深度分析。

## License

Non-commercial use only — see [LICENSE](LICENSE).
