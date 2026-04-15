from personal_digest.infrastructure.llm.openai_provider import OpenAICompatibleLLMProvider
from personal_digest.settings import LLMSettings


def test_llm_provider_parses_json_code_block() -> None:
    provider = OpenAICompatibleLLMProvider(
        LLMSettings(enabled=True, base_url="https://example.com/v1", api_key="token", model="test-model")
    )

    result = provider._parse_analysis_content(
        """```json
        {"summary":"摘要","category":"AI","tags":["agent","rss"],"score":88}
        ```"""
    )

    assert result.summary == "摘要"
    assert result.category == "AI"
    assert result.tags == ["agent", "rss"]
    assert result.score == 88
