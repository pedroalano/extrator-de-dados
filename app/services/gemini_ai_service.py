from __future__ import annotations

import json
import logging
from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from app.config import Settings
from app.services.ai_service import AIService
from app.services.llm_text import truncate_llm_user_prompt

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiAIService(AIService):
    """Cliente da API Gemini (Google AI Studio) via REST."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._api_key = settings.gemini_api_key
        self._base = settings.gemini_base_url.rstrip("/")
        self._model = settings.gemini_model.strip()
        self._http_transport = http_transport

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        if not self._api_key:
            raise ValueError("GEMINI_API_KEY não configurada")

        user_content = truncate_llm_user_prompt(
            user_prompt, self._settings.llm_max_input_chars
        )
        schema_hint = json.dumps(
            response_model.model_json_schema(), ensure_ascii=False
        )[:8000]
        user_text = (
            user_content
            + "\n\nO JSON deve obedecer este schema (referência):\n"
            + schema_hint
        )

        max_out = max_tokens or self._settings.llm_max_tokens
        temp = (
            temperature
            if temperature is not None
            else self._settings.llm_temperature
        )

        body: dict[str, Any] = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_text}],
                }
            ],
            "generationConfig": {
                "temperature": temp,
                "maxOutputTokens": max_out,
                "responseMimeType": "application/json",
            },
        }

        model_id = quote(self._model, safe="")
        url = f"{self._base}/v1beta/models/{model_id}:generateContent"
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        client_kw: dict[str, Any] = {"timeout": self._settings.llm_timeout_seconds}
        if self._http_transport is not None:
            client_kw["transport"] = self._http_transport
        async with httpx.AsyncClient(**client_kw) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = _extract_gemini_json_text(data)
        parsed = json.loads(text)
        return response_model.model_validate(parsed)


def _extract_gemini_json_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    if not candidates:
        logger.error("Resposta Gemini sem candidates: %s", data)
        raise ValueError("Formato de resposta do Gemini inválido (sem candidates)")

    parts = (
        candidates[0].get("content", {}).get("parts") if isinstance(candidates[0], dict) else None
    )
    if not parts or not isinstance(parts, list):
        logger.error("Resposta Gemini sem parts: %s", data)
        raise ValueError("Formato de resposta do Gemini inválido (sem parts)")

    first = parts[0] if parts else {}
    text = first.get("text") if isinstance(first, dict) else None
    if not text or not isinstance(text, str):
        logger.error("Resposta Gemini sem texto: %s", data)
        raise ValueError("Formato de resposta do Gemini inválido (sem texto)")

    return text.strip()
