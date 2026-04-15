# AGENTS.md

本文件面向在本仓库中协作的开发者与 Coding Agent，目的是快速说明项目边界、运行方式和改动约束，避免偏离当前项目主线并出现过度设计。

## 1. 项目定位

`Personal Digest Agent` 是一个单用户、单机常驻的极简信息聚合与摘要工具，不是 RSS Reader 产品，也不是多用户平台。

当前主线仍聚焦这条基础闭环：

`RSS / RSSHub 拉取 -> 去重入库 -> 正文提取 -> LLM 摘要分类评分 -> Digest 生成 -> Email 发送`

明确不做：

- Feed Reader UI
- 用户系统
- 多端同步
- 平台化推荐系统
- 消息队列、复杂规则引擎、过度抽象的插件系统

## 2. 目录职责

```text
.
├── config/
│   ├── settings.yaml      # 应用配置，含数据库、LLM、SMTP、调度
│   └── sources.yaml       # 来源与用户偏好，是真实配置源
├── src/personal_digest/
│   ├── domain/            # 实体、枚举、异常、端口定义
│   ├── application/       # 用例、pipeline 编排、调度服务
│   ├── infrastructure/    # feed/extractor/llm/notify/persistence/rendering 适配器
│   └── interfaces/cli/    # 命令行入口
├── templates/             # Digest 邮件模板
├── tests/                 # 单元测试与集成测试
├── main.py                # 本地脚本入口
└── pyproject.toml         # 依赖与 CLI script 定义
```

## 3. 核心架构

### 3.1 分层原则

- `domain` 只表达业务事实和抽象端口，不依赖外部基础设施。
- `application` 只负责编排 use case，不直接写第三方 SDK 细节。
- `infrastructure` 实现端口，承接外部依赖与 IO。
- `interfaces` 负责把 CLI 输入映射成应用调用。

### 3.2 当前主流程

1. `SyncSourcesUseCase`
   - 启动时将 `config/sources.yaml` 同步到 SQLite 的 `feed_source` 表。
   - 配置中已删除的 source 会被自动置为 `enabled = false`。
2. `PollFeedsUseCase`
   - 拉取到期 source。
   - 使用 `entry_id -> normalized_url` 顺序去重。
3. `ExtractPendingArticlesUseCase`
   - 使用 `Trafilatura -> Readability -> Feed Summary` 进行提取与降级。
   - 使用 `content_hash` 再做一层正文级去重。
4. `AnalyzePendingArticlesUseCase`
   - 调用 OpenAI Compatible 接口产出 `summary/category/tags/score`。
   - LLM 失败时降级为标题/Feed 摘要兜底，不阻断整批任务。
5. `BuildDailyDigestUseCase`
   - 只选择达到 `min_score` 的内容。
   - 先保证分类覆盖，再按总分补齐 Top N。
6. `SendDigestUseCase`
   - Markdown 为持久化正本。
   - HTML 发送时再渲染，不重复存库。

## 4. 配置与环境变量

### 4.1 `config/settings.yaml`

主要配置：

- `app.timezone`
- `app.database_path`
- `app.debug_store_raw_html`
- `app.user_agent`
- `app.initial_fetch_entry_limit`
- `scheduler.poll_interval_minutes`
- `llm.base_url`
- `llm.enabled`
- `llm.api_key`
- `llm.model`
- `notification.email.*`

支持 `${ENV_NAME}` 形式的环境变量替换。

### 4.2 敏感配置与环境变量约束

以下内容必须通过环境变量注入，不应直接写入仓库文件：

- `LLM_API_KEY`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_SENDER`
- `SMTP_RECIPIENTS`

推荐的环境变量名称：

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_SENDER`
- `SMTP_RECIPIENTS`

其中 `SMTP_RECIPIENTS` 支持逗号分隔多个邮箱地址。

在 Windows 上，如果刚新增或修改了用户级环境变量，需要重开终端或重启 Codex App。否则当前进程可能看不到最新值。

如果敏感值曾被写入仓库文件或提交历史，应视为已泄露并尽快轮换。

### 4.3 `config/sources.yaml`

这里是来源与偏好的真实源，不要把来源管理逻辑再做一套数据库 UI。

- `sources[*]`
  - `id`
  - `name`
  - `type`
  - `feed_url`
  - `enabled`
  - `fetch_interval_minutes`
  - `headers`
  - `cookies`
- `preferences`
  - `topics`
  - `excluded_topics`
  - `source_weights`
  - `digest_max_items`
  - `min_score`
  - `digest_send_time`
  - `category_whitelist`

## 5. 常用命令

安装依赖：

```bash
pip install -e .[dev]
```

初始化数据库：

```bash
personal-digest init-db
```

执行来源同步：

```bash
personal-digest sync-sources
```

执行一次拉取、提取、分析：

```bash
personal-digest poll
```

生成并发送指定日期的 Digest：

```bash
personal-digest digest --date 2026-04-15 --send
```

执行完整闭环：

```bash
personal-digest run-once
```

启动常驻调度：

```bash
personal-digest serve
```

运行测试：

```bash
pytest
```

接手排查建议顺序：

1. 确认环境变量在当前进程可见
2. 运行 `pytest`
3. 执行 `personal-digest init-db`
4. 执行 `personal-digest sync-sources`
5. 执行 `personal-digest poll`
6. 需要验证发信时再执行 `personal-digest digest --send`

## 6. 开发约束

### 6.1 代码原则

- 可读性优先，不要为了“架构完整性”做超前抽象。
- 优先 Glue Code First，先复用现有 use case、repository、provider，再考虑新增层级。
- 方法需要在必要处补充 `Why` 注释，使用简体中文。
- 关键失败路径必须保留日志，日志字段至少带 `job_id/source_id/article_id/stage/status` 中的相关上下文。
- 文件编码统一使用 UTF-8 without BOM。

### 6.2 架构边界

- 不要把当前 CLI 主线直接扩成 Web API，除非需求明确发生变化。
- 新增外部能力时，优先通过已有端口模式扩展：
  - `FeedProvider`
  - `ContentExtractor`
  - `LLMProvider`
  - `Notifier`
- 若要新增推送渠道，先实现 `Notifier`，不要把业务逻辑散落在 use case 里。
- 若要新增来源类型，先评估能否继续通过标准 feed URL 接入，避免过早引入专有抓取框架。

### 6.3 测试要求

- 影响去重、提取降级、评分筛选、Digest 组装、通知发送的改动必须补测试。
- 单元测试放 `tests/unit/`，SQLite 真实链路测试放 `tests/integration/`。
- 没有本地 Python 环境时，不要伪造测试结果；需要在提交说明中明确“未执行”。

## 7. 提交建议

- Commit message 使用 Conventional Commits。
- 优先使用 `feat`、`fix`、`refactor`、`docs`、`test`，避免泛化成 `chore`。
- 如果本次提交同时包含代码与文档，scope 应尽量贴近实际改动中心，例如 `digest`、`pipeline`、`docs`。

## 8. 改动前自检清单

提交前至少确认：

- 配置样例与代码实际读取字段一致。
- `run-once` 主链路仍保持可达。
- 新增依赖已写入 `pyproject.toml`。
- 新增文档没有与 `README.md` / `AGENTS.md` 冲突。
- 未引入与当前单机 CLI / SQLite 主线不匹配的过度设计。
