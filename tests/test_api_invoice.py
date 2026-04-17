import pytest

from app.services.pdf_processor import PDF_LLM_INPUT_PDF_NOT_IMPLEMENTED


def test_process_invoice_returns_json(client, minimal_nfe_xml: bytes, sample_pdf_bytes: bytes):
    response = client.post(
        "/process-invoice",
        files={
            "xml_file": ("nfe.xml", minimal_nfe_xml, "application/xml"),
            "pdf_file": ("danfe.pdf", sample_pdf_bytes, "application/pdf"),
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "llm_extracted" in data
    assert data.get("llm_extracted") is None
    assert data["invoice_type"] == "nfe"
    assert data["invoice_number"] == "12345"
    assert data["issuer"]["cnpj"] == "12345678000199"
    assert data["receiver"]["cnpj"] == "98765432000188"
    assert data["total_value"] == 20.0
    assert len(data["items"]) == 1
    assert data["items"][0]["code"] == "001"
    assert "structure_hash" in data
    assert data["extraction_sources"]["xml_mapping"] in ("default", "cached", "llm")


def test_process_invoice_pdf_llm_input_pdf_adds_warning(
    client, minimal_nfe_xml: bytes, sample_pdf_bytes: bytes
):
    response = client.post(
        "/process-invoice",
        data={"pdf_llm_input": "pdf"},
        files={
            "xml_file": ("nfe.xml", minimal_nfe_xml, "application/xml"),
            "pdf_file": ("danfe.pdf", sample_pdf_bytes, "application/pdf"),
        },
    )
    assert response.status_code == 200, response.text
    assert PDF_LLM_INPUT_PDF_NOT_IMPLEMENTED in response.json()["warnings"]


def test_process_invoice_nfse(client, minimal_nfse_xml: bytes, sample_pdf_bytes: bytes):
    response = client.post(
        "/process-invoice",
        files={
            "xml_file": ("nfse.xml", minimal_nfse_xml, "application/xml"),
            "pdf_file": ("nfse.pdf", sample_pdf_bytes, "application/pdf"),
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["invoice_type"] == "nfse"
    assert data["invoice_number"] == "888888"
    assert data["issuer"]["cnpj"] == "11111111000111"
    assert data["receiver"]["cnpj"] == "22222222000122"
    assert data["total_value"] == 150.0
    assert data["taxes"]["iss"] == 3.0
    assert len(data["items"]) == 1


def test_process_invoice_rejects_non_xml(client, sample_pdf_bytes: bytes):
    response = client.post(
        "/process-invoice",
        files={
            "xml_file": ("bad.txt", b"not xml", "text/plain"),
            "pdf_file": ("danfe.pdf", sample_pdf_bytes, "application/pdf"),
        },
    )
    assert response.status_code == 422


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
