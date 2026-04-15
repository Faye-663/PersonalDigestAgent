from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from personal_digest.domain.models import (
    AnalysisResult,
    Article,
    ArticleAnalysis,
    ArticleDigestCandidate,
    DigestRecord,
    ExtractedContent,
    FeedEntry,
    FeedSource,
    SendResult,
)


class FeedProvider(ABC):
    @abstractmethod
    def fetch(self, source: FeedSource) -> list[FeedEntry]:
        raise NotImplementedError


class ContentExtractor(ABC):
    @abstractmethod
    def extract(self, url: str, feed_summary: str | None) -> ExtractedContent:
        raise NotImplementedError


class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, article: Article, preferences: dict) -> AnalysisResult:
        raise NotImplementedError


class Notifier(ABC):
    @abstractmethod
    def send(self, digest_markdown: str, digest_html: str, recipients: list[str], subject: str) -> SendResult:
        raise NotImplementedError


class DigestRenderer(ABC):
    @abstractmethod
    def render_html(self, markdown_text: str, subject: str) -> str:
        raise NotImplementedError


class FeedSourceRepository(ABC):
    @abstractmethod
    def upsert_sources(self, sources: list[FeedSource]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_due_sources(self, now: datetime) -> list[FeedSource]:
        raise NotImplementedError

    @abstractmethod
    def mark_fetch_success(self, source_id: str, fetched_at: datetime) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_fetch_failure(self, source_id: str, failed_at: datetime, error_message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, source_id: str) -> FeedSource | None:
        raise NotImplementedError


class ArticleRepository(ABC):
    @abstractmethod
    def exists_by_entry_id(self, source_id: str, entry_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def exists_by_normalized_url(self, normalized_url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def find_by_content_hash(self, content_hash: str) -> Article | None:
        raise NotImplementedError

    @abstractmethod
    def create(self, article: Article) -> Article:
        raise NotImplementedError

    @abstractmethod
    def list_by_status(self, status: str, limit: int | None = None) -> list[Article]:
        raise NotImplementedError

    @abstractmethod
    def update_after_extraction(
        self,
        article_id: int,
        *,
        clean_content: str,
        content_hash_value: str,
        fallback_used: str,
        raw_html: str | None,
        updated_at: datetime,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_duplicate(self, article_id: int, duplicate_of_article_id: int, updated_at: datetime) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_extraction_failed(self, article_id: int, updated_at: datetime, error_message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_ready(self, article_id: int, updated_at: datetime) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_digest_candidates(self, start_at: datetime, end_at: datetime) -> list[ArticleDigestCandidate]:
        raise NotImplementedError


class AnalysisRepository(ABC):
    @abstractmethod
    def upsert(self, analysis: ArticleAnalysis) -> ArticleAnalysis:
        raise NotImplementedError

    @abstractmethod
    def get_by_article_id(self, article_id: int) -> ArticleAnalysis | None:
        raise NotImplementedError


class DigestRepository(ABC):
    @abstractmethod
    def upsert(self, record: DigestRecord) -> DigestRecord:
        raise NotImplementedError

    @abstractmethod
    def get_by_date(self, digest_date: date) -> DigestRecord | None:
        raise NotImplementedError

    @abstractmethod
    def mark_sent(self, digest_id: int, sent_at: datetime) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, digest_id: int, failed_at: datetime, error_message: str) -> None:
        raise NotImplementedError
