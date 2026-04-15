# Personal Digest Agent 项目背景与需求说明（给 Codex）

## 一、项目背景

目标开发一个 **个人信息聚合与 AI 摘要助手（Personal Digest Agent）**。

需求来源：

- 用户关注大量：
  - 微信公众号
  - 个人博客
  - 小红书博主
  - 其他内容网站
- 每日新增文章很多，质量参差不齐，人工筛选成本高
- 希望系统自动：
  - 拉取新文章
  - 提取正文
  - 生成摘要
  - 分类/打标签
  - 筛选推荐(弱推荐)
  - 推送每日简报

------

## 二、竞品/现成方案调研结论

已调研过现成产品：

### Folo

- Folo 基本满足需求，是 AI RSS Reader
- 提供：
  - Feed 聚合
  - AI 摘要
  - Digest
  - 分类整理
- 但：
  - 功能过多，超出真实需求
  - 需要付费，不符合性价比预期
- 结论：

> 不直接使用 Folo
>  但将其作为 Benchmark / 产品参考

Folo 公开定位与能力可参考：AI RSS Reader，支持 AI 摘要/Digest 等。

------

## 三、核心技术调研结论

------

### 1. 来源获取方案

采用：

```
RSS / Atom / Sitemap
    ↓
RSSHub（主）
    ↓
特殊来源补充方案（后续扩展）
```

#### 原因

RSSHub 已是成熟生态：

- 支持大量网站转 RSS
- 可私有化部署
- 社区成熟

------

#### 已知限制

##### 微信公众号

RSSHub 可支持，但：

- 反爬严格
- 通常需要 Cookie / 配置
- 稳定性一般

##### 小红书

RSSHub 可支持部分 Route，但稳定性一般：

- 某些用户/路由可能超时/失效

------

#### 额外候选（暂不纳入 MVP）

微信公众号增强方案：

- WeWe RSS / we-mp-rss
- 作为未来补充来源方案

------

### 2. 正文提取方案

主方案：

```
Trafilatura（Primary）
Readability（Fallback）
```

原因：

- Trafilatura：正文提取效果优秀，适合生产
- Readability：作为兜底

------

## 四、项目定位（非常重要）

本项目：

> **不是 Folo 替代品**
>
> **不是 RSS Reader 产品**

而是：

> **极简 Personal Digest Pipeline**

仅实现：

```
Feed 拉取
→ 内容提取
→ AI 摘要/分类
→ 每日简报推送
```

------

## 五、明确不做的功能（避免过度设计）

以下功能 **不做 / 非 MVP**：

```
Feed Reader UI
多端同步
收藏夹
复杂搜索
用户系统
推荐算法平台化
社区/分享
复杂权限体系
```

------

## 六、MVP 功能范围

------

### 1. Feed Source 管理

支持配置多个来源：

------

### 2. 定时抓取

定时：

- 拉取 Feed
- 获取新增文章
- 去重入库

------

### 3. 正文提取

对文章链接：

- 抓取 HTML
- 提取正文
- 提取 Metadata

------

### 4. AI 内容处理



------

### 5. Digest 生成

按模板输出摘要等内容

------

### 6. 推送

MVP 先支持：

```
Email
```

预留：

```
Telegram
企业微信
Webhook
```

------

## 七、推荐技术栈

------

### 后端

```
Python 3.11+
```

------

### 框架

```
FastAPI（可选）
```

若无需 API：

可仅脚本化服务。

------

### 调度

```
APScheduler
```

------

### Feed 拉取

```
feedparser
```

------

### 正文提取

```
trafilatura
readability-lxml
```

------

### LLM

抽象 Provider Interface：

```
OpenAI Compatible API
```

要求：

- 可替换不同模型

------

### 存储

MVP：

```
SQLite
```

后续可升级：

```
PostgreSQL
```

------

### 模板

```
Jinja2
```

------

### 推送

```
SMTP
```

------

## 八、推荐系统架构

------

```
FeedScheduler
    ↓
FeedFetcher
    ↓
ArticleDeduplicator
    ↓
ContentExtractor
    ↓
ArticleAnalyzer
    ↓
DigestBuilder
    ↓
Notifier
```

------

## 九、建议目录结构（Python）

------

```
personal-digest-agent/
├── app/
│   ├── domain/
│   │   ├── model/
│   │   ├── service/
│   │   └── repository/
│   │
│   ├── application/
│   │   ├── scheduler/
│   │   ├── pipeline/
│   │   └── usecase/
│   │
│   ├── infrastructure/
│   │   ├── feed/
│   │   ├── extractor/
│   │   ├── llm/
│   │   ├── notify/
│   │   └── persistence/
│   │
│   └── interfaces/
│       └── api/
│
├── templates/
│   └── digest_email.html
│
├── config/
│   └── config.yaml
│
└── main.py
```

------

## 十、关键设计原则

------

### 1. 可扩展 Provider 化

所有外部能力抽象接口：

```
FeedProvider
ContentExtractor
LLMProvider
Notifier
```

------

### 2. Pipeline 化设计

整个处理流程按 Pipeline 组织：

```
Fetch
→ Extract
→ Analyze
→ Digest
→ Notify
```

------

### 3. 可观察性

需记录：

```
抓取失败日志
提取失败日志
LLM 调用失败日志
推送失败日志
```

------

### 4. 容错降级

```
正文提取失败：
→ 使用 Feed Summary

LLM 失败：
→ 跳过摘要，仅保留标题

推送失败：
→ 重试 / 记录
```

------

## 十一、数据库表设计（MVP）

------

### feed_source

```
id
name
type
feed_url
enabled
fetch_interval_minutes
created_at
updated_at
```

------

### article

```
id
source_id
title
url
publish_time
raw_html
clean_content
content_hash
status
created_at
```

------

### article_analysis

```
id
article_id
summary
category
tags
score
created_at
```

------

### digest_record

```
id
digest_date
content
status
sent_at
```

------

## 十二、第一阶段开发任务（请开始执行）

请基于上述需求：

------

### Step 1

输出完整系统设计：

- 类图 / 模块设计
- 接口定义
- Pipeline 设计
- Provider 抽象

------

### Step 2

生成 MVP 可运行代码骨架：

要求：

- 可直接运行
- 生产级目录结构
- 基础日志/配置/异常处理
- 代码清晰可扩展

------

### Step 3

优先实现以下最小闭环：

```
读取 Feed
→ 拉取新增文章
→ 正文提取
→ 调用 LLM 摘要分类
→ 生成 Digest Markdown
→ Email 推送
```

------

## 十三、额外要求

------

### 编码风格

- 优先可读性
- 避免过度抽象
- 生产级可扩展设计
- 不做过度工程化

------

### 输出要求

- 每个模块附设计说明
- 关键类添加注释
- 先设计后编码
- 不要跳过架构设计直接写实现

------

# 补充说明（给 Codex）

这是一个：

> **个人工具 / Side Project**

目标：

> **快速落地 MVP，优先可用性，而非平台化完美设计**