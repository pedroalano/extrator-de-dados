from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

XML_PATH_DISCOVERY_SYSTEM = """Você é um especialista em XML de Nota Fiscal eletrônica brasileira (NFe).
Analise o XML (pode estar truncado) e retorne APENAS um JSON válido com XPaths que usem local-name() para não depender de prefixos de namespace.
Os XPaths devem ser absolutos a partir da raiz do documento (começar com / ou //) exceto product_inner que são relativos a cada nó de produto.
Não invente caminhos: baseie-se apenas nas tags visíveis no trecho.
Campos obrigatórios no JSON: issuer, receiver, invoice_number, date, total_value, products_container, taxes_root.
product_inner é um objeto com chaves: code, description, ncm, quantity, unit, unit_value, total_value (XPaths relativos com .//).
"""

PDF_EXTRACTION_SYSTEM = """Você extrai dados estruturados de texto de DANFE/NFe em português.
Retorne APENAS JSON válido com chaves: issuer_name, issuer_cnpj, receiver_name, receiver_cnpj, invoice_number, date, total_value (número), products (lista de objetos com code, description, quantity, unit_value, total_value quando existir), taxes_note (string livre ou null).
Use null para campos ausentes. Não invente valores."""


def render_template(template: str, **kwargs: Any) -> str:
    return template.format(**kwargs)


class AIService(ABC):
    @abstractmethod
    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        pass


class OpenAICompatibleAIService(AIService):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base = settings.llm_base_url.rstrip("/")
        self._api_key = settings.llm_api_key

    def _truncate(self, text: str) -> str:
        max_c = self._settings.llm_max_input_chars
        if len(text) <= max_c:
            return text
        return text[: max_c // 2] + "\n...[truncado]...\n" + text[-max_c // 2 :]

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

        user_content = self._truncate(user_prompt)
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
        async with httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds) as client:
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


class NullAIService(AIService):
    """Stub para testes ou ambiente sem LLM."""

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> T:
        raise RuntimeError("NullAIService: LLM desabilitado")
