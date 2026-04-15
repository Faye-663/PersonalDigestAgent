from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from pathlib import Path


@dataclass(slots=True)
class EmailSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipients: list[str]
    use_tls: bool
    use_ssl: bool
    subject_prefix: str = "[Personal Digest]"


@dataclass(slots=True)
class LLMSettings:
    enabled: bool
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 60
    temperature: float = 0.2


@dataclass(slots=True)
class AppSettings:
    timezone: str
    database_path: Path
    debug_store_raw_html: bool
    user_agent: str
    poll_interval_minutes: int
    initial_fetch_entry_limit: int
    llm: LLMSettings
    email: EmailSettings


@dataclass(slots=True)
class FeedSourceConfig:
    id: str
    name: str
    type: str
    feed_url: str
    enabled: bool
    fetch_interval_minutes: int
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PreferenceConfig:
    topics: list[str] = field(default_factory=list)
    excluded_topics: list[str] = field(default_factory=list)
    source_weights: dict[str, float] = field(default_factory=dict)
    digest_max_items: int = 8
    min_score: int = 60
    digest_send_time: time = time(hour=8, minute=0)
    category_whitelist: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourcesSettings:
    sources: list[FeedSourceConfig]
    preferences: PreferenceConfig
