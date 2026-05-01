from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

from app.services.prompts import PDF_EXTRACTION_MASTER, XML_PATH_DISCOVERY_NFE

T = TypeVar("T", bound=BaseModel)

XML_PATH_DISCOVERY_SYSTEM = XML_PATH_DISCOVERY_NFE
PDF_EXTRACTION_SYSTEM = PDF_EXTRACTION_MASTER


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
