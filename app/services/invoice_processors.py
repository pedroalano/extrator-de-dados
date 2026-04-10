"""Abstração para processadores XML por tipo de nota."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.repositories import XmlMappingRepository
from app.models.invoice_types import InvoiceType
from app.services.ai_service import AIService
from app.services.nfe_xml_service import process_nfe_xml
from app.services.nfse_xml_service import process_nfse_xml
from app.services.xml_extract_common import XmlProcessResult


class BaseInvoiceProcessor(ABC):
    @abstractmethod
    async def process_xml(
        self, xml_bytes: bytes, *, has_api_key: bool
    ) -> XmlProcessResult:
        raise NotImplementedError


class NfeInvoiceProcessor(BaseInvoiceProcessor):
    def __init__(self, repo: XmlMappingRepository, ai: AIService) -> None:
        self._repo = repo
        self._ai = ai

    async def process_xml(
        self, xml_bytes: bytes, *, has_api_key: bool
    ) -> XmlProcessResult:
        return await process_nfe_xml(
            xml_bytes, has_api_key=has_api_key, repo=self._repo, ai=self._ai
        )


class NfseInvoiceProcessor(BaseInvoiceProcessor):
    def __init__(self, repo: XmlMappingRepository, ai: AIService) -> None:
        self._repo = repo
        self._ai = ai

    async def process_xml(
        self, xml_bytes: bytes, *, has_api_key: bool
    ) -> XmlProcessResult:
        return await process_nfse_xml(
            xml_bytes, has_api_key=has_api_key, repo=self._repo, ai=self._ai
        )


def get_invoice_processor(
    invoice_type: InvoiceType, repo: XmlMappingRepository, ai: AIService
) -> BaseInvoiceProcessor:
    if invoice_type == "nfe":
        return NfeInvoiceProcessor(repo, ai)
    return NfseInvoiceProcessor(repo, ai)
