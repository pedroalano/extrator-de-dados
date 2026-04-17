"""Testes do router POST /extract-pdf (app isolada; não depende de ENABLE_PDF_EXTRACT_ENDPOINT)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_ai_service, get_pdf_processor, get_settings_dep
from app.api.routers.pdf_extract import router as pdf_extract_router
from app.config import Settings
from app.models.ai_schemas import PdfExtractionLLMResponse
from app.services.ai_service import AIService
from app.services.pdf_processor import PDF_LLM_INPUT_PDF_NOT_IMPLEMENTED, PdfProcessor


@pytest.fixture
def pdf_extract_client(fake_ai):
    settings = Settings(
        TESTING=True,
        store_processed_metadata=False,
        llm_api_key="",
        max_upload_bytes=15 * 1024 * 1024,
    )
    app = FastAPI()
    app.include_router(pdf_extract_router)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_ai_service] = lambda: fake_ai
    app.dependency_overrides[get_pdf_processor] = lambda: PdfProcessor(settings, fake_ai)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class _FakePdfExtractLlmAi(AIService):
    async def complete_json(
        self, *, system_prompt, user_prompt, response_model, max_tokens=None, temperature=None
    ):
        if response_model is PdfExtractionLLMResponse:
            return PdfExtractionLLMResponse(invoice_number="LLM-NF-999")
        raise NotImplementedError(response_model)


@pytest.fixture
def pdf_extract_client_llm():
    settings = Settings(
        TESTING=True,
        store_processed_metadata=False,
        llm_api_key="sk-test",
        max_upload_bytes=15 * 1024 * 1024,
    )
    ai = _FakePdfExtractLlmAi()
    app = FastAPI()
    app.include_router(pdf_extract_router)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_ai_service] = lambda: ai
    app.dependency_overrides[get_pdf_processor] = lambda: PdfProcessor(settings, ai)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_extract_pdf_nfe_ok(pdf_extract_client, sample_pdf_bytes: bytes):
    r = pdf_extract_client.post(
        "/extract-pdf",
        params={
            "invoice_type": "nfe",
            "skip_llm": "true",
            "simulate_xml_complete": "false",
        },
        files={"pdf_file": ("danfe.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["invoice_type"] == "nfe"
    assert data["extraction_mode"] == "deterministic"
    assert data["used_llm"] is False
    assert data.get("llm_extracted") is None
    assert "quality_score" in data


def test_extract_pdf_pdf_llm_input_adds_warning(pdf_extract_client, sample_pdf_bytes: bytes):
    r = pdf_extract_client.post(
        "/extract-pdf",
        params={
            "invoice_type": "nfe",
            "skip_llm": "true",
            "simulate_xml_complete": "false",
            "pdf_llm_input": "pdf",
        },
        files={"pdf_file": ("danfe.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert PDF_LLM_INPUT_PDF_NOT_IMPLEMENTED in r.json()["warnings"]


def test_extract_pdf_includes_llm_extracted_when_llm_runs(
    pdf_extract_client_llm, sample_pdf_bytes: bytes
):
    r = pdf_extract_client_llm.post(
        "/extract-pdf",
        params={
            "invoice_type": "nfe",
            "skip_llm": "false",
            "simulate_xml_complete": "false",
        },
        files={"pdf_file": ("danfe.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["used_llm"] is True
    assert data["extraction_mode"] == "llm"
    assert data["llm_extracted"] is not None
    assert data["llm_extracted"]["invoice_number"] == "LLM-NF-999"


def test_extract_pdf_llm_with_pdf_input_still_merges_and_warns(
    pdf_extract_client_llm, sample_pdf_bytes: bytes
):
    r = pdf_extract_client_llm.post(
        "/extract-pdf",
        params={
            "invoice_type": "nfe",
            "skip_llm": "false",
            "simulate_xml_complete": "false",
            "pdf_llm_input": "pdf",
        },
        files={"pdf_file": ("danfe.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["used_llm"] is True
    assert PDF_LLM_INPUT_PDF_NOT_IMPLEMENTED in data["warnings"]
    assert data["llm_extracted"]["invoice_number"] == "LLM-NF-999"


def test_extract_pdf_rejects_non_pdf(pdf_extract_client, sample_pdf_bytes: bytes):
    r = pdf_extract_client.post(
        "/extract-pdf",
        params={"invoice_type": "nfe", "skip_llm": "true"},
        files={"pdf_file": ("x.txt", sample_pdf_bytes, "text/plain")},
    )
    assert r.status_code == 422


def test_simulated_xml_coverage_helpers():
    from app.models.pdf_extract import simulated_xml_coverage

    all_false = simulated_xml_coverage(False)
    assert all(v is False for v in all_false.values())
    all_true = simulated_xml_coverage(True)
    assert all(v is True for v in all_true.values())
    assert set(all_false.keys()) == {
        "issuer",
        "receiver",
        "invoice_number",
        "date",
        "total",
        "items",
    }
