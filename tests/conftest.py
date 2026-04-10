from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import fitz
import pytest

os.environ["TESTING"] = "true"
os.environ["STORE_PROCESSED_METADATA"] = "false"

from app.config import get_settings
from app.main import app
from app.models.ai_schemas import NfseXPathMapping, PdfExtractionLLMResponse, XPathDiscoveryLLMResponse
from app.services.ai_service import AIService
from app.services.nfe_xml_service import default_nfe_xpath_mapping

get_settings.cache_clear()


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def minimal_nfe_xml(fixture_dir: Path) -> bytes:
    return (fixture_dir / "minimal_nfe.xml").read_bytes()


@pytest.fixture
def minimal_nfse_xml(fixture_dir: Path) -> bytes:
    return (fixture_dir / "minimal_nfse.xml").read_bytes()


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), "DANFE Nota Fiscal N 12345")
        page.insert_text((72, 100), "Emitente 12.345.678/0001-99")
        page.insert_text((72, 130), "Destinatario 98.765.432/0001-88")
        page.insert_text((72, 160), "Valor total R$ 20,00")
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture
def fake_mongo():
    xml_col = MagicMock()
    xml_col.find_one = AsyncMock(return_value=None)
    xml_col.update_one = AsyncMock()

    proc_col = MagicMock()
    proc_col.insert_one = AsyncMock()

    db = {
        "xml_mappings": xml_col,
        "processed_invoices": proc_col,
    }
    return db, xml_col, proc_col


class FakeAIService(AIService):
    async def complete_json(self, *, system_prompt, user_prompt, response_model, max_tokens=None, temperature=None):
        if response_model is XPathDiscoveryLLMResponse:
            return default_nfe_xpath_mapping()
        if response_model is NfseXPathMapping:
            return NfseXPathMapping()
        if response_model is PdfExtractionLLMResponse:
            return PdfExtractionLLMResponse()
        raise NotImplementedError(response_model)


@pytest.fixture
def fake_ai() -> FakeAIService:
    return FakeAIService()


@pytest.fixture
def client(fake_mongo, fake_ai):
    from app.api.deps import get_ai_service, get_db

    fake_db, _, _ = fake_mongo

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_ai_service] = lambda: fake_ai

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()
