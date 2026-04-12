from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.config import Settings
from app.services.ai_service import AIService
from app.services.llm_text import truncate_llm_user_prompt

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleAIService(AIService):
    """Cliente de API compatível com OpenAI (Chat Completions + JSON)."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._base = settings.llm_base_url.rstrip("/")
        self._api_key = settings.llm_api_key
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
            raise ValueError("OPENAI_API_KEY não configurada")

        user_content = truncate_llm_user_prompt(
            user_prompt, self._settings.llm_max_input_chars
        )
        schema_hint = json.dumps(
            response_model.model_json_schema(), ensure_ascii=False
        )[:8000]

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_content
                + "\n\nO JSON deve obedecer este schema (referência):\n"
                + schema_hint,
            },
        ]

        payload: dict[str, Any] = {
            "model": self._settings.llm_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens or self._settings.llm_max_tokens,
            "temperature": (
                temperature
                if temperature is not None
                else self._settings.llm_temperature
            ),
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._base}/chat/completions"
        client_kw: dict[str, Any] = {"timeout": self._settings.llm_timeout_seconds}
        if self._http_transport is not None:
            client_kw["transport"] = self._http_transport
        async with httpx.AsyncClient(**client_kw) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error("Resposta LLM inesperada: %s", data)
            raise ValueError("Formato de resposta do LLM inválido") from e

        parsed = json.loads(content)
        return response_model.model_validate(parsed)
