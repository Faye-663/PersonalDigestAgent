from personal_digest.utils import content_hash, load_app_settings, normalize_url


def test_normalize_url_removes_tracking_parameters() -> None:
    url = "https://example.com/post?id=1&utm_source=rss&spm=test#section"
    assert normalize_url(url) == "https://example.com/post?id=1"


def test_content_hash_normalizes_whitespace() -> None:
    assert content_hash("hello   world") == content_hash("hello world")


def test_load_app_settings_supports_comma_separated_recipients(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.yaml").write_text(
        """
app:
  timezone: Asia/Shanghai
  database_path: data/personal_digest.db
  debug_store_raw_html: false
  user_agent: PersonalDigestAgent/0.1
  initial_fetch_entry_limit: 50

scheduler:
  poll_interval_minutes: 5

llm:
  enabled: true
  base_url: "${LLM_BASE_URL}"
  api_key: "${LLM_API_KEY}"
  model: "${LLM_MODEL}"
  timeout_seconds: 60
  temperature: 0.2

notification:
  email:
    host: smtp.gmail.com
    port: 465
    username: "${SMTP_USERNAME}"
    password: "${SMTP_PASSWORD}"
    sender: "${SMTP_SENDER}"
    recipients: "${SMTP_RECIPIENTS}"
    use_tls: false
    use_ssl: true
    subject_prefix: "[Personal Digest]"
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    monkeypatch.setenv("SMTP_SENDER", "sender@example.com")
    monkeypatch.setenv("SMTP_RECIPIENTS", "a@example.com, b@example.com ,c@example.com")

    settings = load_app_settings(config_dir)

    assert settings.llm.base_url == "https://example.com/v1"
    assert settings.email.recipients == ["a@example.com", "b@example.com", "c@example.com"]
