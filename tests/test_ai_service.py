from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.api.deps import get_ai_service
from app.config import Settings
from app.services.openai_ai_service import OpenAICompatibleAIService
from app.services.gemini_ai_service import GeminiAIService


class _DemoSchema(BaseModel):
    foo: str
    n: int


def test_get_ai_service_returns_openai_by_default():
    s = Settings(testing=True, store_processed_metadata=False, llm_provider="openai")
    svc = get_ai_service(s)
    assert isinstance(svc, OpenAICompatibleAIService)


def test_get_ai_service_returns_gemini_when_configured():
    s = Settings(
        testing=True,
        store_processed_metadata=False,
        llm_provider="gemini",
        gemini_api_key="test-key",
    )
    svc = get_ai_service(s)
    assert isinstance(svc, GeminiAIService)


def test_settings_has_llm_credentials():
    assert not Settings(
        testing=True, llm_provider="openai", llm_api_key=""
    ).has_llm_credentials()
    assert Settings(
        testing=True, llm_provider="openai", llm_api_key="sk-x"
    ).has_llm_credentials()
    assert not Settings(
        testing=True, llm_provider="gemini", gemini_api_key=""
    ).has_llm_credentials()
    assert Settings(
        testing=True, llm_provider="gemini", gemini_api_key="g-key"
    ).has_llm_credentials()


@pytest.mark.asyncio
async def test_gemini_complete_json_mock_transport():
    body_out = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps({"foo": "bar", "n": 1})}],
                }
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-goog-api-key") == "k"
        assert request.url.path.endswith(":generateContent")
        return httpx.Response(200, json=body_out)

    transport = httpx.MockTransport(handler)
    s = Settings(
        testing=True,
        store_processed_metadata=False,
        llm_provider="gemini",
        gemini_api_key="k",
        gemini_model="gemini-2.0-flash",
        llm_timeout_seconds=30.0,
    )
    svc = GeminiAIService(s, http_transport=transport)
    out = await svc.complete_json(
        system_prompt="sys",
        user_prompt="user",
        response_model=_DemoSchema,
    )
    assert out.foo == "bar"
    assert out.n == 1


@pytest.mark.asyncio
async def test_gemini_complete_json_raises_without_key():
    s = Settings(testing=True, llm_provider="gemini", gemini_api_key="")
    svc = GeminiAIService(s)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await svc.complete_json(
            system_prompt="s",
            user_prompt="u",
            response_model=_DemoSchema,
        )
