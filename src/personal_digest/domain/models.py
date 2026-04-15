from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class ArticleStatus(StrEnum):
    PENDING_EXTRACTION = "pending_extraction"
    EXTRACTION_FAILED = "extraction_failed"
    PENDING_ANALYSIS = "pending_analysis"
    READY = "ready"
    DUPLICATE = "duplicate"


class DigestStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass(slots=True)
class FeedSource:
    id: str
    name: str
    type: str
    feed_url: str
    enabled: bool
    fetch_interval_minutes: int
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    last_fetched_at: datetime | None = None
    last_error_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class FeedEntry:
    entry_id: str | None
    title: str
    url: str
    published_at: datetime | None
    summary: str | None
    raw_metadata: dict


@dataclass(slots=True)
class Article:
    source_id: str
    title: str
    url: str
    normalized_url: str
    id: int | None = None
    entry_id: str | None = None
    publish_time: datetime | None = None
    feed_summary: str | None = None
    raw_html: str | None = None
    clean_content: str | None = None
    content_hash: str | None = None
    extraction_fallback_used: str | None = None
    status: ArticleStatus = ArticleStatus.PENDING_EXTRACTION
    duplicate_of_article_id: int | None = None
    last_error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ExtractedContent:
    clean_content: str
    metadata: dict[str, str]
    fallback_used: str
    raw_html: str | None = None


@dataclass(slots=True)
class AnalysisResult:
    summary: str
    category: str
    tags: list[str]
    score: int


@dataclass(slots=True)
class ArticleAnalysis:
    article_id: int
    summary: str
    category: str
    tags: list[str]
    score: int
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ArticleDigestCandidate:
    article_id: int
    source_id: str
    source_name: str
    title: str
    url: str
    publish_time: datetime | None
    summary: str
    category: str
    tags: list[str]
    score: int


@dataclass(slots=True)
class DigestRecord:
    digest_date: date
    content_markdown: str
    status: DigestStatus
    id: int | None = None
    sent_at: datetime | None = None
    last_error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class SendResult:
    recipients: list[str]
    message_id: str | None = None

