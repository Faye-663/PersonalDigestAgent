from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from time import perf_counter
from zoneinfo import ZoneInfo

from personal_digest.application.services import build_digest_markdown, select_digest_candidates
from personal_digest.domain.exceptions import ProviderError
from personal_digest.domain.models import (
    AnalysisResult,
    Article,
    ArticleAnalysis,
    ArticleStatus,
    DigestRecord,
    DigestStatus,
    FeedSource,
)
from personal_digest.domain.ports import (
    AnalysisRepository,
    ArticleRepository,
    ContentExtractor,
    DigestRenderer,
    DigestRepository,
    FeedProvider,
    FeedSourceRepository,
    LLMProvider,
    Notifier,
)
from personal_digest.settings import PreferenceConfig
from personal_digest.utils import content_hash, normalize_url, utc_now


@dataclass(slots=True)
class SyncSourcesUseCase:
    source_repository: FeedSourceRepository
    logger: logging.Logger

    def execute(self, sources: list[FeedSource]) -> int:
        """配置文件是单用户场景的真实源，启动时先同步可避免运行态漂移。"""
        self.source_repository.upsert_sources(sources)
        self.logger.info("Synced sources", extra={"stage": "sync_sources", "status": "ok"})
        return len(sources)


@dataclass(slots=True)
class PollFeedsUseCase:
    source_repository: FeedSourceRepository
    article_repository: ArticleRepository
    feed_provider: FeedProvider
    logger: logging.Logger

    def execute(self, now: datetime | None = None) -> int:
        now = now or utc_now()
        created = 0
        for source in self.source_repository.list_due_sources(now):
            started = perf_counter()
            try:
                entries = self.feed_provider.fetch(source)
                for entry in entries:
                    normalized = normalize_url(entry.url)
                    if entry.entry_id and self.article_repository.exists_by_entry_id(source.id, entry.entry_id):
                        continue
                    if self.article_repository.exists_by_normalized_url(normalized):
                        continue
                    article = Article(
                        source_id=source.id,
                        entry_id=entry.entry_id,
                        title=entry.title,
                        url=entry.url,
                        normalized_url=normalized,
                        publish_time=entry.published_at,
                        feed_summary=entry.summary,
                        status=ArticleStatus.PENDING_EXTRACTION,
                    )
                    self.article_repository.create(article)
                    created += 1
                self.source_repository.mark_fetch_success(source.id, now)
                duration_ms = int((perf_counter() - started) * 1000)
                self.logger.info(
                    "Fetched feed entries",
                    extra={
                        "source_id": source.id,
                        "stage": "poll_feeds",
                        "status": "ok",
                        "duration_ms": duration_ms,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self.source_repository.mark_fetch_failure(source.id, now, str(exc))
                duration_ms = int((perf_counter() - started) * 1000)
                self.logger.exception(
                    "Failed to fetch source",
                    extra={
                        "source_id": source.id,
                        "stage": "poll_feeds",
                        "status": "failed",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    },
                )
        return created


@dataclass(slots=True)
class ExtractPendingArticlesUseCase:
    article_repository: ArticleRepository
    extractor: ContentExtractor
    logger: logging.Logger
    store_raw_html: bool = False

    def execute(self, limit: int | None = None) -> int:
        processed = 0
        now = utc_now()
        for article in self.article_repository.list_by_status(ArticleStatus.PENDING_EXTRACTION.value, limit=limit):
            started = perf_counter()
            try:
                extracted = self.extractor.extract(article.url, article.feed_summary)
                current_hash = content_hash(extracted.clean_content)
                duplicated_article = self.article_repository.find_by_content_hash(current_hash)
                if duplicated_article and duplicated_article.id and duplicated_article.id != article.id:
                    self.article_repository.mark_duplicate(article.id or 0, duplicated_article.id, now)
                else:
                    self.article_repository.update_after_extraction(
                        article.id or 0,
                        clean_content=extracted.clean_content,
                        content_hash_value=current_hash,
                        fallback_used=extracted.fallback_used,
                        raw_html=extracted.raw_html if self.store_raw_html else None,
                        updated_at=now,
                    )
                processed += 1
                duration_ms = int((perf_counter() - started) * 1000)
                self.logger.info(
                    "Extracted article content",
                    extra={
                        "article_id": str(article.id or "-"),
                        "source_id": article.source_id,
                        "stage": "extract",
                        "status": "ok",
                        "duration_ms": duration_ms,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self.article_repository.mark_extraction_failed(article.id or 0, now, str(exc))
                duration_ms = int((perf_counter() - started) * 1000)
                self.logger.exception(
                    "Failed to extract article",
                    extra={
                        "article_id": str(article.id or "-"),
                        "source_id": article.source_id,
                        "stage": "extract",
                        "status": "failed",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    },
                )
        return processed


@dataclass(slots=True)
class AnalyzePendingArticlesUseCase:
    article_repository: ArticleRepository
    analysis_repository: AnalysisRepository
    llm_provider: LLMProvider
    preferences: PreferenceConfig
    logger: logging.Logger

    def execute(self, limit: int | None = None) -> int:
        processed = 0
        now = utc_now()
        preference_payload = {
            "topics": self.preferences.topics,
            "excluded_topics": self.preferences.excluded_topics,
            "source_weights": self.preferences.source_weights,
        }
        for article in self.article_repository.list_by_status(ArticleStatus.PENDING_ANALYSIS.value, limit=limit):
            started = perf_counter()
            try:
                result = self.llm_provider.analyze(article, preference_payload)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "LLM analyze failed, fallback to title-only analysis",
                    extra={
                        "article_id": str(article.id or "-"),
                        "source_id": article.source_id,
                        "stage": "analyze",
                        "status": "degraded",
                        "error": str(exc),
                    },
                )
                result = AnalysisResult(
                    summary=(article.feed_summary or article.title or "")[:280] or "LLM 调用失败，本条仅保留标题。",
                    category="未分类",
                    tags=[],
                    score=max(0, self.preferences.min_score - 20),
                )
            analysis = ArticleAnalysis(
                article_id=article.id or 0,
                summary=result.summary,
                category=result.category,
                tags=result.tags,
                score=max(0, min(100, int(result.score))),
            )
            self.analysis_repository.upsert(analysis)
            self.article_repository.mark_ready(article.id or 0, now)
            processed += 1
            duration_ms = int((perf_counter() - started) * 1000)
            self.logger.info(
                "Analyzed article",
                extra={
                    "article_id": str(article.id or "-"),
                    "source_id": article.source_id,
                    "stage": "analyze",
                    "status": "ok",
                    "duration_ms": duration_ms,
                },
            )
        return processed


@dataclass(slots=True)
class BuildDailyDigestUseCase:
    article_repository: ArticleRepository
    digest_repository: DigestRepository
    preferences: PreferenceConfig
    timezone: str
    logger: logging.Logger

    def execute(self, digest_date: date | None = None) -> DigestRecord:
        digest_date = digest_date or datetime.now(ZoneInfo(self.timezone)).date()
        start_at, end_at = _digest_window(digest_date, self.timezone)
        candidates = self.article_repository.list_digest_candidates(start_at, end_at)
        selected = select_digest_candidates(candidates, self.preferences)
        markdown_content = build_digest_markdown(digest_date, selected)
        record = DigestRecord(
            digest_date=digest_date,
            content_markdown=markdown_content,
            status=DigestStatus.PENDING,
        )
        saved = self.digest_repository.upsert(record)
        self.logger.info(
            "Built daily digest",
            extra={"stage": "build_digest", "status": "ok", "job_id": digest_date.isoformat()},
        )
        return saved


@dataclass(slots=True)
class SendDigestUseCase:
    digest_repository: DigestRepository
    renderer: DigestRenderer
    notifier: Notifier
    recipients: list[str]
    subject_prefix: str
    logger: logging.Logger

    def execute(self, digest_date: date) -> DigestRecord:
        record = self.digest_repository.get_by_date(digest_date)
        if not record:
            raise ProviderError(f"Digest for {digest_date.isoformat()} does not exist.")
        if record.status == DigestStatus.SENT:
            return record

        subject = f"{self.subject_prefix} {digest_date.isoformat()}"
        html = self.renderer.render_html(record.content_markdown, subject)
        try:
            self.notifier.send(record.content_markdown, html, self.recipients, subject)
            self.digest_repository.mark_sent(record.id or 0, utc_now())
        except Exception as exc:  # noqa: BLE001
            self.digest_repository.mark_failed(record.id or 0, utc_now(), str(exc))
            self.logger.exception(
                "Failed to send digest",
                extra={"stage": "send_digest", "status": "failed", "error": str(exc), "job_id": digest_date.isoformat()},
            )
            raise
        updated = self.digest_repository.get_by_date(digest_date)
        if not updated:
            raise ProviderError(f"Digest for {digest_date.isoformat()} disappeared after send.")
        self.logger.info(
            "Sent daily digest",
            extra={"stage": "send_digest", "status": "ok", "job_id": digest_date.isoformat()},
        )
        return updated


def _digest_window(digest_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    local_start = datetime.combine(digest_date, time.min, tzinfo=tz)
    local_end = datetime.combine(digest_date, time.max, tzinfo=tz)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)

