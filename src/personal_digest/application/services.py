from __future__ import annotations

from collections import defaultdict
from datetime import date

from personal_digest.domain.models import ArticleDigestCandidate
from personal_digest.settings import PreferenceConfig


def select_digest_candidates(
    candidates: list[ArticleDigestCandidate],
    preferences: PreferenceConfig,
) -> list[ArticleDigestCandidate]:
    filtered = [
        item
        for item in candidates
        if item.score >= preferences.min_score
        and (not preferences.category_whitelist or item.category in preferences.category_whitelist)
    ]
    if not filtered:
        return []

    ordered = sorted(
        filtered,
        key=lambda item: (
            -item.score,
            -(item.publish_time.timestamp() if item.publish_time else 0),
            item.article_id,
        ),
    )

    selected_ids: set[int] = set()
    selected: list[ArticleDigestCandidate] = []
    by_category: dict[str, list[ArticleDigestCandidate]] = defaultdict(list)
    for item in ordered:
        by_category[item.category or "未分类"].append(item)

    # 先保证分类覆盖，避免单一类别挤占整份日报。
    for category in sorted(by_category):
        candidate = by_category[category][0]
        selected.append(candidate)
        selected_ids.add(candidate.article_id)
        if len(selected) >= preferences.digest_max_items:
            return selected

    for item in ordered:
        if item.article_id in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(item.article_id)
        if len(selected) >= preferences.digest_max_items:
            break
    return selected


def build_digest_markdown(digest_date: date, items: list[ArticleDigestCandidate]) -> str:
    if not items:
        return f"# Personal Digest - {digest_date.isoformat()}\n\n今天没有达到阈值的内容。"

    lines = [
        f"# Personal Digest - {digest_date.isoformat()}",
        "",
        f"共筛选出 {len(items)} 篇值得阅读的内容。",
        "",
    ]
    for index, item in enumerate(items, start=1):
        tags = "、".join(item.tags) if item.tags else "无"
        published_at = item.publish_time.strftime("%Y-%m-%d %H:%M") if item.publish_time else "未知"
        lines.extend(
            [
                f"## {index}. {item.title}",
                "",
                f"- 来源：{item.source_name}",
                f"- 发布时间：{published_at}",
                f"- 分类：{item.category}",
                f"- 标签：{tags}",
                f"- 推荐分：{item.score}",
                f"- 链接：{item.url}",
                "",
                item.summary,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"
