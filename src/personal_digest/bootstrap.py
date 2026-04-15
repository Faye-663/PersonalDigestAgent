from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from personal_digest.application.pipeline import PersonalDigestPipeline
from personal_digest.application.scheduler import SchedulerService
from personal_digest.application.use_cases import (
    AnalyzePendingArticlesUseCase,
    BuildDailyDigestUseCase,
    ExtractPendingArticlesUseCase,
    PollFeedsUseCase,
    SendDigestUseCase,
    SyncSourcesUseCase,
)
from personal_digest.domain.models import FeedSource
from personal_digest.infrastructure.extractor import HttpContentExtractor
from personal_digest.infrastructure.feed import FeedparserFeedProvider
from personal_digest.infrastructure.llm import OpenAICompatibleLLMProvider
from personal_digest.infrastructure.notify import SmtpNotifier
from personal_digest.infrastructure.persistence import (
    SQLiteAnalysisRepository,
    SQLiteArticleRepository,
    SQLiteDatabase,
    SQLiteDigestRepository,
    SQLiteFeedSourceRepository,
)
from personal_digest.infrastructure.rendering import JinjaDigestRenderer
from personal_digest.settings import AppSettings, SourcesSettings
from personal_digest.utils import load_app_settings, load_sources_settings


@dataclass(slots=True)
class Application:
    app_settings: AppSettings
    sources_settings: SourcesSettings
    database: SQLiteDatabase
    pipeline: PersonalDigestPipeline
    scheduler: SchedulerService


def create_application(config_dir: Path) -> Application:
    app_settings = load_app_settings(config_dir)
    sources_settings = load_sources_settings(config_dir)
    database = SQLiteDatabase(path=(config_dir.parent / app_settings.database_path).resolve())
    database.initialize()

    logger = logging.getLogger("personal_digest")
    source_repository = SQLiteFeedSourceRepository(database)
    article_repository = SQLiteArticleRepository(database)
    analysis_repository = SQLiteAnalysisRepository(database)
    digest_repository = SQLiteDigestRepository(database)

    configured_sources = [_to_feed_source(item) for item in sources_settings.sources]
    pipeline = PersonalDigestPipeline(
        sync_sources_use_case=SyncSourcesUseCase(source_repository=source_repository, logger=logger),
        poll_feeds_use_case=PollFeedsUseCase(
            source_repository=source_repository,
            article_repository=article_repository,
            feed_provider=FeedparserFeedProvider(
                user_agent=app_settings.user_agent,
                initial_fetch_entry_limit=app_settings.initial_fetch_entry_limit,
            ),
            logger=logger,
        ),
        extract_pending_articles_use_case=ExtractPendingArticlesUseCase(
            article_repository=article_repository,
            extractor=HttpContentExtractor(user_agent=app_settings.user_agent),
            logger=logger,
            store_raw_html=app_settings.debug_store_raw_html,
        ),
        analyze_pending_articles_use_case=AnalyzePendingArticlesUseCase(
            article_repository=article_repository,
            analysis_repository=analysis_repository,
            llm_provider=OpenAICompatibleLLMProvider(app_settings.llm),
            preferences=sources_settings.preferences,
            logger=logger,
            llm_enabled=app_settings.llm.enabled,
        ),
        build_daily_digest_use_case=BuildDailyDigestUseCase(
            article_repository=article_repository,
            digest_repository=digest_repository,
            preferences=sources_settings.preferences,
            timezone=app_settings.timezone,
            logger=logger,
        ),
        send_digest_use_case=SendDigestUseCase(
            digest_repository=digest_repository,
            renderer=JinjaDigestRenderer(template_dir=(config_dir.parent / "templates").resolve()),
            notifier=SmtpNotifier(app_settings.email),
            recipients=app_settings.email.recipients,
            subject_prefix=app_settings.email.subject_prefix,
            logger=logger,
        ),
        configured_sources=configured_sources,
    )
    scheduler = SchedulerService(
        pipeline=pipeline,
        app_settings=app_settings,
        preferences=sources_settings.preferences,
        logger=logger,
    )
    return Application(
        app_settings=app_settings,
        sources_settings=sources_settings,
        database=database,
        pipeline=pipeline,
        scheduler=scheduler,
    )


def _to_feed_source(source_config) -> FeedSource:
    return FeedSource(
        id=source_config.id,
        name=source_config.name,
        type=source_config.type,
        feed_url=source_config.feed_url,
        enabled=source_config.enabled,
        fetch_interval_minutes=source_config.fetch_interval_minutes,
        headers=source_config.headers,
        cookies=source_config.cookies,
    )
