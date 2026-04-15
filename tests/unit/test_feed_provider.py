from datetime import UTC, datetime
from types import SimpleNamespace

from personal_digest.domain.models import FeedSource
from personal_digest.infrastructure.feed.feedparser_provider import FeedparserFeedProvider


def test_feed_provider_limits_initial_fetch_to_recent_entries(monkeypatch) -> None:
    provider = FeedparserFeedProvider(user_agent="test-agent", initial_fetch_entry_limit=2)
    source = FeedSource(
        id="source-a",
        name="Source A",
        type="rss",
        feed_url="https://example.com/feed.xml",
        enabled=True,
        fetch_interval_minutes=30,
    )
    feed = SimpleNamespace(
        status=200,
        entries=[
            {
                "id": "older",
                "title": "Older",
                "link": "https://example.com/older",
                "published_parsed": datetime(2026, 4, 15, 8, 0, tzinfo=UTC).timetuple(),
            },
            {
                "id": "newest",
                "title": "Newest",
                "link": "https://example.com/newest",
                "published_parsed": datetime(2026, 4, 15, 10, 0, tzinfo=UTC).timetuple(),
            },
            {
                "id": "middle",
                "title": "Middle",
                "link": "https://example.com/middle",
                "published_parsed": datetime(2026, 4, 15, 9, 0, tzinfo=UTC).timetuple(),
            },
        ],
    )
    monkeypatch.setattr(
        "personal_digest.infrastructure.feed.feedparser_provider.feedparser.parse",
        lambda *args, **kwargs: feed,
    )

    entries = provider.fetch(source)

    assert [entry.entry_id for entry in entries] == ["newest", "middle"]


def test_feed_provider_does_not_limit_existing_source(monkeypatch) -> None:
    provider = FeedparserFeedProvider(user_agent="test-agent", initial_fetch_entry_limit=1)
    source = FeedSource(
        id="source-a",
        name="Source A",
        type="rss",
        feed_url="https://example.com/feed.xml",
        enabled=True,
        fetch_interval_minutes=30,
        last_fetched_at=datetime(2026, 4, 15, 8, 0, tzinfo=UTC),
    )
    feed = SimpleNamespace(
        status=200,
        entries=[
            {"id": "1", "title": "One", "link": "https://example.com/1"},
            {"id": "2", "title": "Two", "link": "https://example.com/2"},
        ],
    )
    monkeypatch.setattr(
        "personal_digest.infrastructure.feed.feedparser_provider.feedparser.parse",
        lambda *args, **kwargs: feed,
    )

    entries = provider.fetch(source)

    assert [entry.entry_id for entry in entries] == ["1", "2"]
