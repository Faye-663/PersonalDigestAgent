# Personal Digest Agent

`Personal Digest Agent` 是一个单用户、单机常驻的极简信息聚合与摘要工具。

## MVP 能力

- 从 `RSS / Atom / RSSHub` 拉取来源
- 对新增文章去重入库
- 使用 `Trafilatura -> Readability -> Feed Summary` 提取正文
- 使用 OpenAI Compatible API 生成摘要、分类、标签与弱推荐分
- 生成 Digest Markdown，并渲染为 HTML 邮件
- 使用 SMTP 发送每日简报

## 目录

```text
.
├── AGENTS.md
├── config/
│   ├── settings.yaml
│   └── sources.yaml
├── src/personal_digest/
├── templates/
└── tests/
```

## 架构概览

项目采用轻量 DDD 分层：

- `domain`：实体、枚举、异常、端口定义
- `application`：用例编排、Digest 选择、调度服务
- `infrastructure`：Feed 抓取、正文提取、LLM、SMTP、SQLite、模板渲染
- `interfaces/cli`：命令行入口

默认主流程：

`sync sources -> poll feeds -> extract -> analyze -> build digest -> send digest`

## 快速开始

1. 创建 Python 3.11 虚拟环境并安装依赖：

```bash
pip install -e .[dev]
```

2. 按需修改：

- `config/settings.yaml`
- `config/sources.yaml`
- 设置环境变量：
  - `LLM_BASE_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL`
  - `SMTP_USERNAME`
  - `SMTP_PASSWORD`
  - `SMTP_SENDER`
  - `SMTP_RECIPIENTS`，多个收件人使用逗号分隔

敏感信息不要直接写入仓库配置文件。`config/settings.yaml` 应保持占位符形式，由环境变量在运行时注入。

3. 初始化数据库：

```bash
personal-digest init-db
```

4. 执行一次完整闭环：

```bash
personal-digest run-once
```

5. 启动常驻调度：

```bash
personal-digest serve
```

## 主要命令

- `personal-digest init-db`
- `personal-digest sync-sources`
- `personal-digest poll`
- `personal-digest digest --send`
- `personal-digest run-once`
- `personal-digest serve`

## 协作说明

更详细的仓库协作说明、架构边界和改动约束见 [AGENTS.md](AGENTS.md)。

## 项目进度

当前项目阶段、已完成进度与生命周期管理建议见 [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)。
