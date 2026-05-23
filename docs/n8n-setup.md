# n8n Webhook 集成指南

将 n8n 定时触发的 Reddit 搜索结果推送到本地 Webhook。

为了避免后台自动化意外消耗 DeepSeek 额度，Webhook 现在只入库并返回 `run_id`，不会在 HTTP 请求里直接触发 AI 分析。

## 前提条件

- n8n 已安装并运行（桌面版或 self-hosted）
- Reddit Demand Radar 项目已配置 `.env`
- `.env` 已配置 `WEBHOOK_TOKEN`
- Webhook 服务已启动：`uvicorn webhook.server:app --port 8000`

`.env` 示例：

```bash
WEBHOOK_TOKEN=<your-random-long-token>
```

如果要分析 n8n 推送的这批帖子，复制 Webhook 返回的 `run_id`，再手动运行：

```bash
python main.py --analyze-run <run_id>
```

## n8n 工作流配置

### 节点 1：Schedule Trigger

设置定时触发间隔：

- **Trigger Interval**: 每 6 小时（或按需调整）
- 类型：`Schedule Trigger` → `Interval`

### 节点 2：HTTP Request — 搜索 Reddit

调用 Reddit 公开 JSON API 搜索帖子：

- **Method**: GET
- **URL**: `https://www.reddit.com/r/SideProject/search.json?q=need a tool&sort=relevance&restrict_sr=on&limit=25`
- 参数说明：
  - `q`: 搜索关键词（URL 编码）
  - `restrict_sr=on`: 限定子版块
  - `sort=relevance`: 按相关性排序
  - `limit`: 每次返回数量

Reddit 公开 API 无需认证，但有频率限制（约 60 次/分钟）。如需搜索全站，去掉 `restrict_sr=on` 并修改路径为 `/search.json`。

### 节点 3：Code — 转换为 Webhook 格式

将 Reddit API 返回的数据转换为 Webhook 接受的 JSON 格式。

```javascript
// 将 Reddit API 返回的 children 转为 webhook 格式
const items = [];
for (const child of $input.first().json.data.children) {
  const data = child.data;
  items.push({
    title: data.title,
    body: data.selftext || "",
    url: "https://www.reddit.com" + data.permalink,
    subreddit: data.subreddit,
    score: data.score,
    num_comments: data.num_comments,
    created_utc: data.created_utc,
    reddit_id: data.id
  });
}
return items;
```

注意：Code 节点的 Mode 设为 "Run Once for All Items"，返回格式为数组。

### 节点 4：HTTP Request — 推送到本地 Webhook

- **Method**: POST
- **URL**: `http://localhost:8000/webhook/posts`
- **Content-Type**: `application/json`
- **Header**: `X-Webhook-Token: 你的 WEBHOOK_TOKEN`
- **Body**: 使用节点 3 的输出

在 "Parameters" 中勾选 "Send Body" → "JSON"，内容直接引用上一个节点的输出。
同时在 "Send Headers" 中添加 `X-Webhook-Token`，值填 `.env` 中的 `WEBHOOK_TOKEN`。

## 完整工作流总结

```
Schedule Trigger (每N小时)
  → HTTP Request (搜索 Reddit)
  → Code (转换为 webhook JSON)
  → HTTP Request (POST 到 localhost:8000/webhook/posts)
```

推送后，Webhook 服务会：
1. 去重写入 SQLite
2. 创建一次 `run_id`
3. 返回 `analysis_status: not_started`
4. 需要分析时手动运行 `python main.py --analyze-run <run_id>`

## 启动所有服务

### 终端 1：Webhook 服务

```bash
cd reddit-demand-radar
source venv/bin/activate
uvicorn webhook.server:app --port 8000 --host 0.0.0.0
```

### 终端 2：Streamlit 面板

```bash
cd reddit-demand-radar
source venv/bin/activate
streamlit run ui/app.py
```

## 常见问题

### n8n 推送后返回 400 错误

检查请求体格式，确保是数组 `[{...}]` 而非单对象 `{...}`。每个对象至少需要 `title` 字段。

### n8n 推送后返回 401 或 503

- `401`：Header 里的 `X-Webhook-Token` 不对。
- `503`：本项目 `.env` 没有配置 `WEBHOOK_TOKEN`。这是故意的保护，避免 Webhook 被误触发后消耗 AI 额度。

### n8n 推送后没有自动分析

这是当前设计。Webhook 只负责入库并创建 `run_id`，避免后台自动扣费。复制返回的 `run_id` 后运行：

```bash
python main.py --analyze-run <run_id>
```

### n8n 推送后返回 413

单次推送超过 `webhook.max_posts_per_request`。减少 Reddit 搜索的 `limit`，或在 `config.yaml` 中调整上限，最大不要超过 100。

### 同一帖子被反复分析

Webhook 端使用 `reddit_id` 做 `INSERT OR IGNORE`，相同 ID 的帖子不会被重复插入。如果没传 `reddit_id`，系统会用 URL 生成稳定 ID。确保 Code 节点正确设置了 `reddit_id: data.id`。

### Reddit API 返回空或限流

- 检查 URL 中的子版块名是否正确
- 尝试减少 `limit` 参数
- Reddit 公开 API 每分钟约 60 次请求，避免频率过高
- 添加 HTTP Request 的 "Retry on Fail" 选项

### Webhook 连接被拒

- 确认 uvicorn 在运行：`curl http://localhost:8000/health`
- 如果 n8n 在 Docker 中运行，需要使用 `host.docker.internal` 替代 `localhost`
