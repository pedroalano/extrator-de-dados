"""Testes unitários do PdfProcessor.extract_text (pdfplumber + fallback PyMuPDF)."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services.pdf_processor import PdfProcessor, _extract_text_pdfplumber

from tests.conftest import FakeAIService


@pytest.fixture
def pdf_processor(fake_ai: FakeAIService) -> PdfProcessor:
    return PdfProcessor(Settings(), fake_ai)


def test_extract_text_sample_pdf_contains_key_content(
    pdf_processor: PdfProcessor, sample_pdf_bytes: bytes
) -> None:
    text, size = pdf_processor.extract_text(sample_pdf_bytes)
    assert size == len(sample_pdf_bytes)
    assert len(text.strip()) >= 60
    lower = text.lower()
    assert "danfe" in lower
    assert "12345" in text
    assert "12.345.678/0001-99" in text
    assert "valor total" in lower or "r$" in lower


def test_extract_text_uses_pymupdf_when_pdfplumber_too_short(
    monkeypatch: pytest.MonkeyPatch,
    pdf_processor: PdfProcessor,
    sample_pdf_bytes: bytes,
) -> None:
    monkeypatch.setattr(
        "app.services.pdf_processor._extract_text_pdfplumber",
        lambda _b: "short",
    )
    text, _ = pdf_processor.extract_text(sample_pdf_bytes)
    assert "DANFE" in text or "danfe" in text.lower()


def test_extract_text_prefers_pdfplumber_when_substantial(
    sample_pdf_bytes: bytes,
) -> None:
    direct = _extract_text_pdfplumber(sample_pdf_bytes)
    assert len(direct.strip()) >= 60
