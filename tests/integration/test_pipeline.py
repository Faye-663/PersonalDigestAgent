from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from personal_digest.application.pipeline import PersonalDigestPipeline
from personal_digest.application.use_cases import (
    AnalyzePendingArticlesUseCase,
    BuildDailyDigestUseCase,
    ExtractPendingArticlesUseCase,
    PollFeedsUseCase,
    SendDigestUseCase,
    SyncSourcesUseCase,
)
from personal_digest.domain.models import (
    AnalysisResult,
    Article,
    ArticleStatus,
    ExtractedContent,
    FeedEntry,
    FeedSource,
    SendResult,
)
from personal_digest.infrastructure.persistence import (
    SQLiteAnalysisRepository,
    SQLiteArticleRepository,
    SQLiteDatabase,
    SQLiteDigestRepository,
    SQLiteFeedSourceRepository,
)
from personal_digest.infrastructure.rendering import JinjaDigestRenderer
from personal_digest.settings import PreferenceConfig
from personal_digest.utils import load_sources_settings


class FakeFeedProvider:
    def __init__(self, entries_by_source: dict[str, list[FeedEntry]]) -> None:
        self.entries_by_source = entries_by_source

    def fetch(self, source: FeedSource) -> list[FeedEntry]:
        return self.entries_by_source[source.id]


class FakeExtractor:
    def __init__(self, payloads: dict[str, ExtractedContent]) -> None:
        self.payloads = payloads

    def extract(self, url: str, feed_summary: str | None) -> ExtractedContent:
        return self.payloads[url]


class FakeLLMProvider:
    def __init__(self, payloads: dict[str, AnalysisResult], failing_titles: set[str] | None = None) -> None:
        self.payloads = payloads
        self.failing_titles = failing_titles or set()

    def analyze(self, article, preferences: dict) -> AnalysisResult:
        if article.title in self.failing_titles:
            raise RuntimeError("LLM unavailable")
        return self.payloads[article.url]


@dataclass(slots=True)
class FakeNotifier:
    sent_messages: list[dict]

    def send(self, digest_markdown: str, digest_html: str, recipients: list[str], subject: str):
        self.sent_messages.append(
            {
                "markdown": digest_markdown,
                "html": digest_html,
                "recipients": recipients,
                "subject": subject,
            }
        )
        return SendResult(recipients=recipients, message_id=subject)


def test_pipeline_run_once_and_yaml_sync(tmp_path: Path) -> None:
    today = datetime.now(UTC).date()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text(
        """
sources:
  - id: source-a
    name: Source A
    type: rss
    feed_url: https://example.com/feed.xml
    enabled: true
    fetch_interval_minutes: 30
    headers: {}
    cookies: {}
preferences:
  topics: [AI, agents]
  excluded_topics: []
  source_weights: {source-a: 1.0}
  digest_max_items: 8
  min_score: 60
  digest_send_time: "08:00"
  category_whitelist: []
        """.strip(),
        encoding="utf-8",
    )

    sources_settings = load_sources_settings(config_dir)
    database = SQLiteDatabase(tmp_path / "digest.db")
    database.initialize()

    source_repository = SQLiteFeedSourceRepository(database)
    article_repository = SQLiteArticleRepository(database)
    analysis_repository = SQLiteAnalysisRepository(database)
    digest_repository = SQLiteDigestRepository(database)

    entries = {
        "source-a": [
            FeedEntry(
                entry_id="1",
                title="Agent A",
                url="https://example.com/a?utm_source=rss",
                published_at=datetime(today.year, today.month, today.day, 0, 0, tzinfo=UTC),
                summary="A summary",
                raw_metadata={},
            ),
            FeedEntry(
                entry_id="2",
                title="Agent B duplicate",
                url="https://example.com/b",
                published_at=datetime(today.year, today.month, today.day, 1, 0, tzinfo=UTC),
                summary="B summary",
                raw_metadata={},
            ),
            FeedEntry(
                entry_id="3",
                title="Agent C",
                url="https://example.com/c",
                published_at=datetime(today.year, today.month, today.day, 2, 0, tzinfo=UTC),
                summary="C summary",
                raw_metadata={},
            ),
        ]
    }
    extracted_payloads = {
        "https://example.com/a?utm_source=rss": ExtractedContent(
            clean_content="Same content block",
            metadata={},
            fallback_used="trafilatura",
            raw_html="<html></html>",
        ),
        "https://example.com/b": ExtractedContent(
            clean_content="Same content block",
            metadata={},
            fallback_used="trafilatura",
            raw_html="<html></html>",
        ),
        "https://example.com/c": ExtractedContent(
            clean_content="Unique content block",
            metadata={},
            fallback_used="readability",
            raw_html="<html></html>",
        ),
    }
    llm_payloads = {
        "https://example.com/a?utm_source=rss": AnalysisResult(
            summary="Article A summary",
            category="AI",
            tags=["ai"],
            score=92,
        ),
        "https://example.com/c": AnalysisResult(
            summary="Article C summary",
            category="Tools",
            tags=["tooling"],
            score=81,
        ),
    }
    notifier = FakeNotifier(sent_messages=[])
    template_dir = Path(__file__).resolve().parents[2] / "templates"
    pipeline = PersonalDigestPipeline(
        sync_sources_use_case=SyncSourcesUseCase(
            source_repository=source_repository,
            logger=_noop_logger(),
        ),
        poll_feeds_use_case=PollFeedsUseCase(
            source_repository=source_repository,
            article_repository=article_repository,
            feed_provider=FakeFeedProvider(entries),
            logger=_noop_logger(),
        ),
        extract_pending_articles_use_case=ExtractPendingArticlesUseCase(
            article_repository=article_repository,
            extractor=FakeExtractor(extracted_payloads),
            logger=_noop_logger(),
            store_raw_html=False,
        ),
        analyze_pending_articles_use_case=AnalyzePendingArticlesUseCase(
            article_repository=article_repository,
            analysis_repository=analysis_repository,
            llm_provider=FakeLLMProvider(llm_payloads),
            preferences=sources_settings.preferences,
            logger=_noop_logger(),
        ),
        build_daily_digest_use_case=BuildDailyDigestUseCase(
            article_repository=article_repository,
            digest_repository=digest_repository,
            preferences=sources_settings.preferences,
            timezone="UTC",
            logger=_noop_logger(),
        ),
        send_digest_use_case=SendDigestUseCase(
            digest_repository=digest_repository,
            renderer=JinjaDigestRenderer(template_dir=template_dir),
            notifier=notifier,
            recipients=["digest@example.com"],
            subject_prefix="[Digest]",
            logger=_noop_logger(),
        ),
        configured_sources=[
            FeedSource(
                id=source.id,
                name=source.name,
                type=source.type,
                feed_url=source.feed_url,
                enabled=source.enabled,
                fetch_interval_minutes=source.fetch_interval_minutes,
                headers=source.headers,
                cookies=source.cookies,
            )
            for source in sources_settings.sources
        ],
    )

    result = pipeline.run_once(today)

    assert result["poll"] == {"fetched": 3, "extracted": 3, "analyzed": 2}
    assert result["digest"] == {"digest_date": today.isoformat(), "status": "sent"}
    digest = digest_repository.get_by_date(today)
    assert digest is not None
    assert digest.status.value == "sent"
    assert notifier.sent_messages
    assert "Agent A" in notifier.sent_messages[0]["markdown"]
    assert "Agent C" in notifier.sent_messages[0]["markdown"]
    assert "Agent B duplicate" not in notifier.sent_messages[0]["markdown"]
    assert source_repository.get_by_id("source-a") is not None


def test_analyze_use_case_degrades_when_llm_fails(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "digest.db")
    database.initialize()
    article_repository = SQLiteArticleRepository(database)
    analysis_repository = SQLiteAnalysisRepository(database)

    article = article_repository.create(
        Article(
            source_id="source-a",
            entry_id="1",
            title="Fallback Article",
            url="https://example.com/fallback",
            normalized_url="https://example.com/fallback",
            clean_content="Fallback content",
            status=ArticleStatus.PENDING_ANALYSIS,
        )
    )

    use_case = AnalyzePendingArticlesUseCase(
        article_repository=article_repository,
        analysis_repository=analysis_repository,
        llm_provider=FakeLLMProvider({}, failing_titles={"Fallback Article"}),
        preferences=PreferenceConfig(min_score=60),
        logger=_noop_logger(),
    )

    processed = use_case.execute()
    analysis = analysis_repository.get_by_article_id(article.id or 0)

    assert processed == 1
    assert analysis is not None
    assert analysis.category == "未分类"
    assert analysis.score == 40


def test_source_repository_marks_removed_sources_disabled_and_honors_due_interval(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "digest.db")
    database.initialize()
    source_repository = SQLiteFeedSourceRepository(database)

    source_repository.upsert_sources(
        [
            FeedSource(
                id="source-a",
                name="Source A",
                type="rss",
                feed_url="https://example.com/feed-a.xml",
                enabled=True,
                fetch_interval_minutes=30,
            ),
            FeedSource(
                id="source-b",
                name="Source B",
                type="rss",
                feed_url="https://example.com/feed-b.xml",
                enabled=True,
                fetch_interval_minutes=60,
            ),
        ]
    )
    source_repository.mark_fetch_success("source-a", datetime(2026, 4, 15, 8, 0, tzinfo=UTC))
    source_repository.mark_fetch_success("source-b", datetime(2026, 4, 15, 8, 30, tzinfo=UTC))

    due = source_repository.list_due_sources(datetime(2026, 4, 15, 8, 45, tzinfo=UTC))
    assert [source.id for source in due] == ["source-a"]

    source_repository.upsert_sources(
        [
            FeedSource(
                id="source-a",
                name="Source A",
                type="rss",
                feed_url="https://example.com/feed-a.xml",
                enabled=True,
                fetch_interval_minutes=30,
            )
        ]
    )

    removed = source_repository.get_by_id("source-b")
    assert removed is not None
    assert removed.enabled is False


def _noop_logger():
    import logging

    logger = logging.getLogger("test.personal_digest")
    logger.handlers.clear()
    logger.propagate = False
    return logger
