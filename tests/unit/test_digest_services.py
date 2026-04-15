from datetime import UTC, date, datetime

from personal_digest.application.services import build_digest_markdown, select_digest_candidates
from personal_digest.domain.models import ArticleDigestCandidate
from personal_digest.settings import PreferenceConfig


def test_select_digest_candidates_respects_threshold_and_category_coverage() -> None:
    preferences = PreferenceConfig(digest_max_items=3, min_score=60)
    candidates = [
        ArticleDigestCandidate(
            article_id=1,
            source_id="s1",
            source_name="Source 1",
            title="A",
            url="https://example.com/a",
            publish_time=datetime(2026, 4, 15, 9, 0, tzinfo=UTC),
            summary="A summary",
            category="AI",
            tags=["ai"],
            score=95,
        ),
        ArticleDigestCandidate(
            article_id=2,
            source_id="s1",
            source_name="Source 1",
            title="B",
            url="https://example.com/b",
            publish_time=datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
            summary="B summary",
            category="Tools",
            tags=["tools"],
            score=82,
        ),
        ArticleDigestCandidate(
            article_id=3,
            source_id="s1",
            source_name="Source 1",
            title="C",
            url="https://example.com/c",
            publish_time=datetime(2026, 4, 15, 11, 0, tzinfo=UTC),
            summary="C summary",
            category="AI",
            tags=["ai"],
            score=78,
        ),
        ArticleDigestCandidate(
            article_id=4,
            source_id="s1",
            source_name="Source 1",
            title="D",
            url="https://example.com/d",
            publish_time=datetime(2026, 4, 15, 11, 30, tzinfo=UTC),
            summary="D summary",
            category="Other",
            tags=["other"],
            score=50,
        ),
    ]

    selected = select_digest_candidates(candidates, preferences)

    assert [item.article_id for item in selected] == [1, 2, 3]


def test_build_digest_markdown_outputs_digest_sections() -> None:
    markdown = build_digest_markdown(
        date(2026, 4, 15),
        [
            ArticleDigestCandidate(
                article_id=1,
                source_id="s1",
                source_name="Source 1",
                title="A",
                url="https://example.com/a",
                publish_time=datetime(2026, 4, 15, 9, 0, tzinfo=UTC),
                summary="A summary",
                category="AI",
                tags=["ai"],
                score=95,
            )
        ],
    )

    assert "# Personal Digest - 2026-04-15" in markdown
    assert "## 1. A" in markdown
    assert "A summary" in markdown

