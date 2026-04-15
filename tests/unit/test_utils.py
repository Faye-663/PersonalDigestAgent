from personal_digest.utils import content_hash, normalize_url


def test_normalize_url_removes_tracking_parameters() -> None:
    url = "https://example.com/post?id=1&utm_source=rss&spm=test#section"
    assert normalize_url(url) == "https://example.com/post?id=1"


def test_content_hash_normalizes_whitespace() -> None:
    assert content_hash("hello   world") == content_hash("hello world")

