from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from personal_digest.application.use_cases import (
    AnalyzePendingArticlesUseCase,
    BuildDailyDigestUseCase,
    ExtractPendingArticlesUseCase,
    PollFeedsUseCase,
    SendDigestUseCase,
    SyncSourcesUseCase,
)
from personal_digest.domain.models import FeedSource


@dataclass(slots=True)
class PersonalDigestPipeline:
    sync_sources_use_case: SyncSourcesUseCase
    poll_feeds_use_case: PollFeedsUseCase
    extract_pending_articles_use_case: ExtractPendingArticlesUseCase
    analyze_pending_articles_use_case: AnalyzePendingArticlesUseCase
    build_daily_digest_use_case: BuildDailyDigestUseCase
    send_digest_use_case: SendDigestUseCase
    configured_sources: list[FeedSource]

    def sync_sources(self) -> int:
        return self.sync_sources_use_case.execute(self.configured_sources)

    def run_poll_cycle(self) -> dict[str, int]:
        self.sync_sources()
        fetched = self.poll_feeds_use_case.execute()
        extracted = self.extract_pending_articles_use_case.execute()
        analyzed = self.analyze_pending_articles_use_case.execute()
        return {"fetched": fetched, "extracted": extracted, "analyzed": analyzed}

    def run_digest_cycle(self, digest_date: date | None = None, *, send: bool = True) -> dict[str, str]:
        record = self.build_daily_digest_use_case.execute(digest_date)
        if send:
            sent_record = self.send_digest_use_case.execute(record.digest_date)
            return {"digest_date": sent_record.digest_date.isoformat(), "status": sent_record.status.value}
        return {"digest_date": record.digest_date.isoformat(), "status": record.status.value}

    def run_once(self, digest_date: date | None = None) -> dict[str, object]:
        poll_result = self.run_poll_cycle()
        digest_result = self.run_digest_cycle(digest_date, send=True)
        return {"poll": poll_result, "digest": digest_result}

