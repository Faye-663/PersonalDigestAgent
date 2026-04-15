from __future__ import annotations

import calendar
from datetime import UTC, datetime
from dataclasses import dataclass

import feedparser

from personal_digest.domain.exceptions import ProviderError
from personal_digest.domain.models import FeedEntry, FeedSource
from personal_digest.domain.ports import FeedProvider


@dataclass(slots=True)
class FeedparserFeedProvider(FeedProvider):
    user_agent: str
    initial_fetch_entry_limit: int = 50

    def fetch(self, source: FeedSource) -> list[FeedEntry]:
        headers = {"User-Agent": self.user_agent, **source.headers}
        if source.cookies:
            headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in source.cookies.items())
        feed = feedparser.parse(source.feed_url, request_headers=headers)
        status = getattr(feed, "status", 200)
        if status >= 400:
            raise ProviderError(f"Feed returned HTTP {status}: {source.feed_url}")

        entries: list[FeedEntry] = []
        for item in feed.entries:
            entries.append(
                FeedEntry(
                    entry_id=item.get("id") or item.get("guid"),
                    title=item.get("title", "Untitled"),
                    url=item.get("link", ""),
                    published_at=_parse_entry_datetime(item),
                    summary=item.get("summary") or item.get("description"),
                    raw_metadata=dict(item),
                )
            )
        if source.last_fetched_at is None and self.initial_fetch_entry_limit > 0:
            # 首次接入只取最近一小批，避免一次性回填数百篇历史文章拖垮首轮验证。
            entries.sort(key=lambda entry: entry.published_at.timestamp() if entry.published_at else float("-inf"), reverse=True)
            return entries[: self.initial_fetch_entry_limit]
        return entries


def _parse_entry_datetime(item: dict) -> datetime | None:
    parsed = item.get("published_parsed") or item.get("updated_parsed")
    if not parsed:
        return None
    timestamp = calendar.timegm(parsed)
    return datetime.fromtimestamp(timestamp, tz=UTC)
