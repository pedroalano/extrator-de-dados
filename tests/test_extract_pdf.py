"""Testes do router POST /extract-pdf (app isolada; não depende de ENABLE_PDF_EXTRACT_ENDPOINT)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_ai_service, get_pdf_processor, get_settings_dep
from app.api.routers.pdf_extract import router as pdf_extract_router
from app.config import Settings
from app.services.pdf_processor import PdfProcessor


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
    assert "quality_score" in data


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
