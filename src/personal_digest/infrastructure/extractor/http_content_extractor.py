from __future__ import annotations

from dataclasses import dataclass

import httpx
import trafilatura
from lxml import html as lxml_html
from readability import Document

from personal_digest.domain.exceptions import ProviderError
from personal_digest.domain.models import ExtractedContent
from personal_digest.domain.ports import ContentExtractor


@dataclass(slots=True)
class HttpContentExtractor(ContentExtractor):
    user_agent: str
    timeout_seconds: int = 20

    def extract(self, url: str, feed_summary: str | None) -> ExtractedContent:
        html = self._fetch_html(url)
        return self._extract_from_html(html, feed_summary)

    def _fetch_html(self, url: str) -> str:
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def _extract_from_html(self, html: str, feed_summary: str | None) -> ExtractedContent:
        # Trafilatura 的正文提取质量更稳，先用它保证主路径效果。
        primary = trafilatura.extract(html, include_comments=False, include_links=False, favor_precision=True)
        if primary:
            return ExtractedContent(clean_content=primary.strip(), metadata={}, fallback_used="trafilatura", raw_html=html)

        try:
            readability_doc = Document(html)
            readability_html = readability_doc.summary()
            readability_text = lxml_html.fromstring(readability_html).text_content().strip()
            if readability_text:
                return ExtractedContent(
                    clean_content=readability_text,
                    metadata={"title": readability_doc.short_title()},
                    fallback_used="readability",
                    raw_html=html,
                )
        except Exception:  # noqa: BLE001
            pass

        if feed_summary:
            return ExtractedContent(
                clean_content=feed_summary.strip(),
                metadata={},
                fallback_used="feed_summary",
                raw_html=html,
            )

        raise ProviderError("Content extraction failed and no feed summary fallback was available.")
