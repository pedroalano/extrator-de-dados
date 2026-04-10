"""Fachada de processamento XML: roteia NFe ou NFS-e."""

from __future__ import annotations

from app.db.repositories import XmlMappingRepository
from app.models.invoice_types import InvoiceType
from app.services.ai_service import AIService
from app.services.nfe_xml_service import process_nfe_xml
from app.services.nfse_xml_service import process_nfse_xml
from app.services.xml_extract_common import XmlProcessResult


class XmlProcessor:
    def __init__(
        self,
        repo: XmlMappingRepository,
        ai: AIService,
    ) -> None:
        self._repo = repo
        self._ai = ai

    async def process(
        self,
        xml_bytes: bytes,
        *,
        has_api_key: bool,
        invoice_type: InvoiceType,
    ) -> XmlProcessResult:
        if invoice_type == "nfe":
            return await process_nfe_xml(
                xml_bytes,
                has_api_key=has_api_key,
                repo=self._repo,
                ai=self._ai,
            )
        return await process_nfse_xml(
            xml_bytes,
            has_api_key=has_api_key,
            repo=self._repo,
            ai=self._ai,
        )
