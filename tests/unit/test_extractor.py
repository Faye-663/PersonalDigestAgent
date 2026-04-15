from personal_digest.infrastructure.extractor.http_content_extractor import HttpContentExtractor


def test_extractor_falls_back_to_readability(monkeypatch) -> None:
    extractor = HttpContentExtractor(user_agent="test-agent")
    html = """
    <html>
      <head><title>Test</title></head>
      <body>
        <article><h1>Title</h1><p>Hello world</p></article>
      </body>
    </html>
    """
    monkeypatch.setattr(
        "personal_digest.infrastructure.extractor.http_content_extractor.trafilatura.extract",
        lambda *args, **kwargs: None,
    )

    result = extractor._extract_from_html(html, None)

    assert result.fallback_used == "readability"
    assert "Hello world" in result.clean_content


def test_extractor_falls_back_to_feed_summary(monkeypatch) -> None:
    extractor = HttpContentExtractor(user_agent="test-agent")
    html = "<html><body><div>empty</div></body></html>"
    monkeypatch.setattr(
        "personal_digest.infrastructure.extractor.http_content_extractor.trafilatura.extract",
        lambda *args, **kwargs: None,
    )

    class BrokenDocument:
        def __init__(self, _: str) -> None:
            pass

        def summary(self) -> str:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "personal_digest.infrastructure.extractor.http_content_extractor.Document",
        BrokenDocument,
    )

    result = extractor._extract_from_html(html, "feed summary text")

    assert result.fallback_used == "feed_summary"
    assert result.clean_content == "feed summary text"

