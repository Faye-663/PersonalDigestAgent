from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, date, datetime, time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from personal_digest.settings import (
    AppSettings,
    EmailSettings,
    FeedSourceConfig,
    LLMSettings,
    PreferenceConfig,
    SourcesSettings,
)

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
_TRACKING_KEYS = {"spm", "si", "from", "source", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def load_yaml(path: Path) -> dict:
    raw_text = path.read_text(encoding="utf-8")
    expanded = _ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), ""), raw_text)
    return yaml.safe_load(expanded) or {}


def load_app_settings(config_dir: Path) -> AppSettings:
    data = load_yaml(config_dir / "settings.yaml")
    app = data.get("app", {})
    scheduler = data.get("scheduler", {})
    llm = data.get("llm", {})
    notification = data.get("notification", {}).get("email", {})

    return AppSettings(
        timezone=app.get("timezone", "Asia/Shanghai"),
        database_path=Path(app.get("database_path", "data/personal_digest.db")),
        debug_store_raw_html=bool(app.get("debug_store_raw_html", False)),
        user_agent=app.get("user_agent", "PersonalDigestAgent/0.1"),
        poll_interval_minutes=int(scheduler.get("poll_interval_minutes", 5)),
        llm=LLMSettings(
            base_url=llm.get("base_url", "https://api.openai.com/v1"),
            api_key=llm.get("api_key", ""),
            model=llm.get("model", "gpt-4o-mini"),
            timeout_seconds=int(llm.get("timeout_seconds", 60)),
            temperature=float(llm.get("temperature", 0.2)),
        ),
        email=EmailSettings(
            host=notification.get("host", ""),
            port=int(notification.get("port", 587)),
            username=notification.get("username", ""),
            password=notification.get("password", ""),
            sender=notification.get("sender", ""),
            recipients=list(notification.get("recipients", [])),
            use_tls=bool(notification.get("use_tls", True)),
            use_ssl=bool(notification.get("use_ssl", False)),
            subject_prefix=notification.get("subject_prefix", "[Personal Digest]"),
        ),
    )


def load_sources_settings(config_dir: Path) -> SourcesSettings:
    data = load_yaml(config_dir / "sources.yaml")
    preference_data = data.get("preferences", {})
    send_time = parse_time(preference_data.get("digest_send_time", "08:00"))
    return SourcesSettings(
        sources=[
            FeedSourceConfig(
                id=item["id"],
                name=item["name"],
                type=item.get("type", "rss"),
                feed_url=item["feed_url"],
                enabled=bool(item.get("enabled", True)),
                fetch_interval_minutes=int(item.get("fetch_interval_minutes", 30)),
                headers=dict(item.get("headers", {})),
                cookies=dict(item.get("cookies", {})),
            )
            for item in data.get("sources", [])
        ],
        preferences=PreferenceConfig(
            topics=list(preference_data.get("topics", [])),
            excluded_topics=list(preference_data.get("excluded_topics", [])),
            source_weights={key: float(value) for key, value in dict(preference_data.get("source_weights", {})).items()},
            digest_max_items=int(preference_data.get("digest_max_items", 8)),
            min_score=int(preference_data.get("min_score", 60)),
            digest_send_time=send_time,
            category_whitelist=list(preference_data.get("category_whitelist", [])),
        ),
    )


def parse_time(value: str) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def from_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def dumps_json(value: dict | list | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def loads_json(value: str | None, *, default: dict | list) -> dict | list:
    if not value:
        return default
    return json.loads(value)


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    filtered_query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_KEYS and not key.lower().startswith("utm_")
    ]
    normalized_path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), normalized_path, urlencode(filtered_query), ""))


def content_hash(text: str) -> str:
    normalized = " ".join(text.split()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

