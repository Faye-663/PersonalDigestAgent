from __future__ import annotations

import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from personal_digest.application.pipeline import PersonalDigestPipeline
from personal_digest.settings import AppSettings, PreferenceConfig


@dataclass(slots=True)
class SchedulerService:
    pipeline: PersonalDigestPipeline
    app_settings: AppSettings
    preferences: PreferenceConfig
    logger: logging.Logger

    def build_scheduler(self) -> BlockingScheduler:
        timezone = ZoneInfo(self.app_settings.timezone)
        scheduler = BlockingScheduler(timezone=timezone)
        scheduler.add_job(
            self._run_poll_job,
            trigger=IntervalTrigger(minutes=self.app_settings.poll_interval_minutes, timezone=timezone),
            id="poll_job",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.add_job(
            self._run_digest_job,
            trigger=CronTrigger(
                hour=self.preferences.digest_send_time.hour,
                minute=self.preferences.digest_send_time.minute,
                timezone=timezone,
            ),
            id="digest_job",
            replace_existing=True,
            max_instances=1,
        )
        return scheduler

    def run(self) -> None:
        scheduler = self.build_scheduler()
        self.logger.info("Starting scheduler", extra={"stage": "scheduler", "status": "ok"})
        scheduler.start()

    def _run_poll_job(self) -> None:
        self.pipeline.run_poll_cycle()

    def _run_digest_job(self) -> None:
        self.pipeline.run_digest_cycle(send=True)
