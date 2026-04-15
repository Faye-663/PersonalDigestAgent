from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from personal_digest.domain.exceptions import ConfigurationError, ProviderError
from personal_digest.domain.models import AnalysisResult, Article
from personal_digest.domain.ports import LLMProvider
from personal_digest.settings import LLMSettings

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


@dataclass(slots=True)
class OpenAICompatibleLLMProvider(LLMProvider):
    settings: LLMSettings

    def analyze(self, article: Article, preferences: dict) -> AnalysisResult:
        if not self.settings.api_key:
            raise ConfigurationError("LLM api_key is missing.")

        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个个人信息摘要助手。请输出 JSON，字段严格为 "
                        "summary/category/tags/score。score 为 0-100 的整数，表示内容质量与用户兴趣的弱推荐混合分。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(article, preferences),
                },
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"}
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=self.settings.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise ProviderError(f"LLM request failed with HTTP {response.status_code}: {response.text}")
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected LLM response: {data}") from exc
        return self._parse_analysis_content(content)

    def _build_prompt(self, article: Article, preferences: dict) -> str:
        return (
            f"标题：{article.title}\n"
            f"来源：{article.source_id}\n"
            f"正文：{article.clean_content or article.feed_summary or article.title}\n\n"
            f"关注主题：{preferences.get('topics', [])}\n"
            f"排斥主题：{preferences.get('excluded_topics', [])}\n"
            f"来源权重：{preferences.get('source_weights', {})}\n\n"
            "要求：\n"
            "1. summary 使用简体中文，80-160 字。\n"
            "2. category 给出单个分类。\n"
            "3. tags 是字符串数组，最多 5 个。\n"
            "4. score 是 0-100 的整数。\n"
        )

    def _parse_analysis_content(self, content: str) -> AnalysisResult:
        json_text = self._extract_json_text(content)
        data = json.loads(json_text)
        summary = str(data.get("summary", "")).strip()
        category = str(data.get("category", "未分类")).strip() or "未分类"
        tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
        score = int(data.get("score", 0))
        return AnalysisResult(summary=summary, category=category, tags=tags, score=score)

    def _extract_json_text(self, content: str) -> str:
        if content.strip().startswith("{"):
            return content
        match = _JSON_BLOCK_RE.search(content)
        if match:
            return match.group(1)
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return content[start : end + 1]
        raise ProviderError(f"LLM output is not valid JSON: {content}")

