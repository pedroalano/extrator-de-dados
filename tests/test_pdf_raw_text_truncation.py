"""Limite configurável de caracteres em PdfSideData.raw_text."""

from __future__ import annotations

import fitz
import pytest

from app.config import Settings
from app.models.pdf_extract import simulated_xml_coverage
from app.services.ai_service import AIService
from app.services.pdf_processor import PdfProcessor


class _NoopAi(AIService):
    async def complete_json(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("LLM não deve ser chamado neste teste")


@pytest.mark.asyncio
async def test_raw_text_respects_pdf_raw_text_max_chars():
    doc = fitz.open()
    try:
        page = doc.new_page()
        chunk = "abcdefghij" * 80
        page.insert_text((72, 72), chunk)
        page.insert_text((72, 92), chunk)
        pdf_bytes = doc.tobytes()
    finally:
        doc.close()

    max_chars = 120
    settings = Settings(
        TESTING=True,
        store_processed_metadata=False,
        llm_api_key="",
        pdf_raw_text_max_chars=max_chars,
    )
    proc = PdfProcessor(settings, _NoopAi())
    out = await proc.process(
        pdf_bytes,
        skip_llm=True,
        has_api_key=False,
        xml_coverage=simulated_xml_coverage(False),
        invoice_type="nfe",
    )
    assert len(out.raw_text) <= max_chars
