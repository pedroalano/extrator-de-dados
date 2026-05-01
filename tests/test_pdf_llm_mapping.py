"""Regressão: JSON aninhado do LLM (Master Prompt) → PdfSideData."""

from __future__ import annotations

from app.models.ai_schemas import (
    PdfDocumentInfo,
    PdfExtractionLLMResponse,
    PdfLineExtract,
    PdfPartyExtract,
    PdfTaxesExtract,
    PdfTotalsExtract,
)
from app.services.pdf_processor import _llm_response_to_side


def test_llm_nested_response_maps_to_pdf_side_data():
    raw = PdfExtractionLLMResponse(
        document_info=PdfDocumentInfo(
            document_kind="nfe",
            invoice_number="123",
            date="2024-01-15",
        ),
        issuer=PdfPartyExtract(name="Emit SA", cnpj="12345678000199"),
        receiver=PdfPartyExtract(name="Dest Ltda"),
        items=[
            PdfLineExtract(
                code="001",
                description="Produto",
                quantity=2.0,
                unit_price=10.5,
                total_price=21.0,
                ncm="12345678",
            )
        ],
        taxes=PdfTaxesExtract(note="ICMS destacado", iss=None),
        totals=PdfTotalsExtract(total_value=99.9),
    )
    side = _llm_response_to_side(raw)
    assert side.invoice_number == "123"
    assert side.date == "2024-01-15"
    assert side.issuer is not None and side.issuer.name == "Emit SA"
    assert side.receiver is not None and side.receiver.name == "Dest Ltda"
    assert len(side.items) == 1
    assert side.items[0].unit_value == 10.5
    assert side.items[0].total_value == 21.0
    assert side.items[0].ncm == "12345678"
    assert side.total_value == 99.9
    assert side.taxes_note == "ICMS destacado"
    assert side.iss is None


def test_llm_taxes_dict_iss_and_note():
    raw = PdfExtractionLLMResponse(
        document_info=PdfDocumentInfo(invoice_number="1"),
        taxes={"note": "obs", "iss": 12.5},
    )
    side = _llm_response_to_side(raw)
    assert side.taxes_note == "obs"
    assert side.iss == 12.5
