from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from personal_digest.domain.models import (
    Article,
    ArticleAnalysis,
    ArticleDigestCandidate,
    ArticleStatus,
    DigestRecord,
    DigestStatus,
    FeedSource,
)
from personal_digest.domain.ports import AnalysisRepository, ArticleRepository, DigestRepository, FeedSourceRepository
from personal_digest.utils import dumps_json, from_iso, loads_json, to_iso, utc_now

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS feed_source (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    feed_url TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    fetch_interval_minutes INTEGER NOT NULL,
    headers_json TEXT NOT NULL DEFAULT '{}',
    cookies_json TEXT NOT NULL DEFAULT '{}',
    last_fetched_at TEXT,
    last_error_at TEXT,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    entry_id TEXT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    publish_time TEXT,
    feed_summary TEXT,
    raw_html TEXT,
    clean_content TEXT,
    content_hash TEXT,
    extraction_fallback_used TEXT,
    status TEXT NOT NULL,
    duplicate_of_article_id INTEGER,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES feed_source(id),
    FOREIGN KEY(duplicate_of_article_id) REFERENCES article(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_article_source_entry
ON article(source_id, entry_id)
WHERE entry_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_article_normalized_url
ON article(normalized_url);

CREATE INDEX IF NOT EXISTS idx_article_status ON article(status);
CREATE INDEX IF NOT EXISTS idx_article_content_hash ON article(content_hash);

CREATE TABLE IF NOT EXISTS article_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL UNIQUE,
    summary TEXT NOT NULL,
    category TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    score INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(article_id) REFERENCES article(id)
);

CREATE INDEX IF NOT EXISTS idx_article_analysis_score ON article_analysis(score);

CREATE TABLE IF NOT EXISTS digest_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_date TEXT NOT NULL UNIQUE,
    content_markdown TEXT NOT NULL,
    status TEXT NOT NULL,
    sent_at TEXT,
    last_error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass(slots=True)
class SQLiteDatabase:
    path: Path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


@dataclass(slots=True)
class SQLiteFeedSourceRepository(FeedSourceRepository):
    database: SQLiteDatabase

    def upsert_sources(self, sources: list[FeedSource]) -> None:
        now = utc_now()
        source_ids = {source.id for source in sources}
        with self.database.connect() as connection:
            for source in sources:
                existing = connection.execute("SELECT created_at FROM feed_source WHERE id = ?", (source.id,)).fetchone()
                created_at = existing["created_at"] if existing else to_iso(now)
                connection.execute(
                    """
                    INSERT INTO feed_source (
                        id, name, type, feed_url, enabled, fetch_interval_minutes,
                        headers_json, cookies_json, last_fetched_at, last_error_at, last_error_message, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        type = excluded.type,
                        feed_url = excluded.feed_url,
                        enabled = excluded.enabled,
                        fetch_interval_minutes = excluded.fetch_interval_minutes,
                        headers_json = excluded.headers_json,
                        cookies_json = excluded.cookies_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        source.id,
                        source.name,
                        source.type,
                        source.feed_url,
                        int(source.enabled),
                        source.fetch_interval_minutes,
                        dumps_json(source.headers),
                        dumps_json(source.cookies),
                        to_iso(source.last_fetched_at),
                        to_iso(source.last_error_at),
                        None,
                        created_at,
                        to_iso(now),
                    ),
                )
            if source_ids:
                placeholders = ", ".join("?" for _ in source_ids)
                connection.execute(
                    f"UPDATE feed_source SET enabled = 0, updated_at = ? WHERE id NOT IN ({placeholders})",
                    [to_iso(now), *source_ids],
                )
            else:
                connection.execute(
                    "UPDATE feed_source SET enabled = 0, updated_at = ?",
                    (to_iso(now),),
                )

    def list_due_sources(self, now: datetime) -> list[FeedSource]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM feed_source WHERE enabled = 1 ORDER BY id").fetchall()
        due: list[FeedSource] = []
        for row in rows:
            source = _row_to_feed_source(row)
            if source.last_fetched_at is None:
                due.append(source)
                continue
            next_run = source.last_fetched_at + timedelta(minutes=source.fetch_interval_minutes)
            if next_run <= now.astimezone(UTC):
                due.append(source)
        return due

    def mark_fetch_success(self, source_id: str, fetched_at: datetime) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE feed_source
                SET last_fetched_at = ?, updated_at = ?, last_error_message = NULL
                WHERE id = ?
                """,
                (to_iso(fetched_at), to_iso(fetched_at), source_id),
            )

    def mark_fetch_failure(self, source_id: str, failed_at: datetime, error_message: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE feed_source
                SET last_error_at = ?, last_error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (to_iso(failed_at), error_message, to_iso(failed_at), source_id),
            )

    def get_by_id(self, source_id: str) -> FeedSource | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM feed_source WHERE id = ?", (source_id,)).fetchone()
        return _row_to_feed_source(row) if row else None


@dataclass(slots=True)
class SQLiteArticleRepository(ArticleRepository):
    database: SQLiteDatabase

    def exists_by_entry_id(self, source_id: str, entry_id: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM article WHERE source_id = ? AND entry_id = ? LIMIT 1",
                (source_id, entry_id),
            ).fetchone()
        return row is not None

    def exists_by_normalized_url(self, normalized_url: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM article WHERE normalized_url = ? LIMIT 1",
                (normalized_url,),
            ).fetchone()
        return row is not None

    def find_by_content_hash(self, content_hash: str) -> Article | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM article
                WHERE content_hash = ? AND status != 'duplicate'
                ORDER BY id ASC
                LIMIT 1
                """,
                (content_hash,),
            ).fetchone()
        return _row_to_article(row) if row else None

    def create(self, article: Article) -> Article:
        now = utc_now()
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO article (
                    source_id, entry_id, title, url, normalized_url, publish_time,
                    feed_summary, raw_html, clean_content, content_hash,
                    extraction_fallback_used, status, duplicate_of_article_id,
                    last_error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.source_id,
                    article.entry_id,
                    article.title,
                    article.url,
                    article.normalized_url,
                    to_iso(article.publish_time),
                    article.feed_summary,
                    article.raw_html,
                    article.clean_content,
                    article.content_hash,
                    article.extraction_fallback_used,
                    article.status.value,
                    article.duplicate_of_article_id,
                    article.last_error_message,
                    to_iso(now),
                    to_iso(now),
                ),
            )
            article.id = int(cursor.lastrowid)
            article.created_at = now
            article.updated_at = now
        return article

    def list_by_status(self, status: str, limit: int | None = None) -> list[Article]:
        query = "SELECT * FROM article WHERE status = ? ORDER BY created_at ASC"
        params: list = [status]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_article(row) for row in rows]

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
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE article
                SET clean_content = ?, content_hash = ?, extraction_fallback_used = ?,
                    raw_html = ?, status = 'pending_analysis', last_error_message = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (clean_content, content_hash_value, fallback_used, raw_html, to_iso(updated_at), article_id),
            )

    def mark_duplicate(self, article_id: int, duplicate_of_article_id: int, updated_at: datetime) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE article
                SET status = 'duplicate', duplicate_of_article_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (duplicate_of_article_id, to_iso(updated_at), article_id),
            )

    def mark_extraction_failed(self, article_id: int, updated_at: datetime, error_message: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE article
                SET status = 'extraction_failed', last_error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (error_message, to_iso(updated_at), article_id),
            )

    def mark_ready(self, article_id: int, updated_at: datetime) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE article SET status = 'ready', updated_at = ?, last_error_message = NULL WHERE id = ?",
                (to_iso(updated_at), article_id),
            )

    def list_digest_candidates(self, start_at: datetime, end_at: datetime) -> list[ArticleDigestCandidate]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    article.id AS article_id,
                    article.source_id AS source_id,
                    feed_source.name AS source_name,
                    article.title AS title,
                    article.url AS url,
                    article.publish_time AS publish_time,
                    article_analysis.summary AS summary,
                    article_analysis.category AS category,
                    article_analysis.tags_json AS tags_json,
                    article_analysis.score AS score
                FROM article
                JOIN article_analysis ON article_analysis.article_id = article.id
                JOIN feed_source ON feed_source.id = article.source_id
                WHERE article.status = 'ready'
                  AND article.created_at >= ?
                  AND article.created_at <= ?
                ORDER BY article_analysis.score DESC, article.created_at DESC
                """,
                (to_iso(start_at), to_iso(end_at)),
            ).fetchall()
        return [
            ArticleDigestCandidate(
                article_id=int(row["article_id"]),
                source_id=row["source_id"],
                source_name=row["source_name"],
                title=row["title"],
                url=row["url"],
                publish_time=from_iso(row["publish_time"]),
                summary=row["summary"],
                category=row["category"],
                tags=list(loads_json(row["tags_json"], default=[])),
                score=int(row["score"]),
            )
            for row in rows
        ]


@dataclass(slots=True)
class SQLiteAnalysisRepository(AnalysisRepository):
    database: SQLiteDatabase

    def upsert(self, analysis: ArticleAnalysis) -> ArticleAnalysis:
        now = utc_now()
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT id, created_at FROM article_analysis WHERE article_id = ?",
                (analysis.article_id,),
            ).fetchone()
            created_at = existing["created_at"] if existing else to_iso(now)
            connection.execute(
                """
                INSERT INTO article_analysis (
                    article_id, summary, category, tags_json, score, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    summary = excluded.summary,
                    category = excluded.category,
                    tags_json = excluded.tags_json,
                    score = excluded.score,
                    updated_at = excluded.updated_at
                """,
                (
                    analysis.article_id,
                    analysis.summary,
                    analysis.category,
                    dumps_json(analysis.tags),
                    analysis.score,
                    created_at,
                    to_iso(now),
                ),
            )
            row = connection.execute(
                "SELECT * FROM article_analysis WHERE article_id = ?",
                (analysis.article_id,),
            ).fetchone()
        return _row_to_analysis(row)

    def get_by_article_id(self, article_id: int) -> ArticleAnalysis | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM article_analysis WHERE article_id = ?",
                (article_id,),
            ).fetchone()
        return _row_to_analysis(row) if row else None


@dataclass(slots=True)
class SQLiteDigestRepository(DigestRepository):
    database: SQLiteDatabase

    def upsert(self, record: DigestRecord) -> DigestRecord:
        now = utc_now()
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT id, created_at, sent_at FROM digest_record WHERE digest_date = ?",
                (record.digest_date.isoformat(),),
            ).fetchone()
            created_at = existing["created_at"] if existing else to_iso(now)
            sent_at = existing["sent_at"] if existing else None
            connection.execute(
                """
                INSERT INTO digest_record (
                    digest_date, content_markdown, status, sent_at, last_error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(digest_date) DO UPDATE SET
                    content_markdown = excluded.content_markdown,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    last_error_message = NULL
                """,
                (
                    record.digest_date.isoformat(),
                    record.content_markdown,
                    record.status.value,
                    sent_at,
                    record.last_error_message,
                    created_at,
                    to_iso(now),
                ),
            )
            row = connection.execute(
                "SELECT * FROM digest_record WHERE digest_date = ?",
                (record.digest_date.isoformat(),),
            ).fetchone()
        return _row_to_digest(row)

    def get_by_date(self, digest_date: date) -> DigestRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM digest_record WHERE digest_date = ?",
                (digest_date.isoformat(),),
            ).fetchone()
        return _row_to_digest(row) if row else None

    def mark_sent(self, digest_id: int, sent_at: datetime) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE digest_record
                SET status = ?, sent_at = ?, updated_at = ?, last_error_message = NULL
                WHERE id = ?
                """,
                (DigestStatus.SENT.value, to_iso(sent_at), to_iso(sent_at), digest_id),
            )

    def mark_failed(self, digest_id: int, failed_at: datetime, error_message: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE digest_record
                SET status = ?, updated_at = ?, last_error_message = ?
                WHERE id = ?
                """,
                (DigestStatus.FAILED.value, to_iso(failed_at), error_message, digest_id),
            )


def _row_to_feed_source(row: sqlite3.Row) -> FeedSource:
    return FeedSource(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        feed_url=row["feed_url"],
        enabled=bool(row["enabled"]),
        fetch_interval_minutes=int(row["fetch_interval_minutes"]),
        headers=dict(loads_json(row["headers_json"], default={})),
        cookies=dict(loads_json(row["cookies_json"], default={})),
        last_fetched_at=from_iso(row["last_fetched_at"]),
        last_error_at=from_iso(row["last_error_at"]),
        created_at=from_iso(row["created_at"]),
        updated_at=from_iso(row["updated_at"]),
    )


def _row_to_article(row: sqlite3.Row) -> Article:
    return Article(
        id=int(row["id"]),
        source_id=row["source_id"],
        entry_id=row["entry_id"],
        title=row["title"],
        url=row["url"],
        normalized_url=row["normalized_url"],
        publish_time=from_iso(row["publish_time"]),
        feed_summary=row["feed_summary"],
        raw_html=row["raw_html"],
        clean_content=row["clean_content"],
        content_hash=row["content_hash"],
        extraction_fallback_used=row["extraction_fallback_used"],
        status=ArticleStatus(row["status"]),
        duplicate_of_article_id=row["duplicate_of_article_id"],
        last_error_message=row["last_error_message"],
        created_at=from_iso(row["created_at"]),
        updated_at=from_iso(row["updated_at"]),
    )


def _row_to_analysis(row: sqlite3.Row) -> ArticleAnalysis:
    return ArticleAnalysis(
        id=int(row["id"]),
        article_id=int(row["article_id"]),
        summary=row["summary"],
        category=row["category"],
        tags=list(loads_json(row["tags_json"], default=[])),
        score=int(row["score"]),
        created_at=from_iso(row["created_at"]),
        updated_at=from_iso(row["updated_at"]),
    )


def _row_to_digest(row: sqlite3.Row) -> DigestRecord:
    return DigestRecord(
        id=int(row["id"]),
        digest_date=date.fromisoformat(row["digest_date"]),
        content_markdown=row["content_markdown"],
        status=DigestStatus(row["status"]),
        sent_at=from_iso(row["sent_at"]),
        last_error_message=row["last_error_message"],
        created_at=from_iso(row["created_at"]),
        updated_at=from_iso(row["updated_at"]),
    )
