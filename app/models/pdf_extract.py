from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai_schemas import PdfExtractionLLMResponse
from app.models.domain import LineItem, Party
from app.models.invoice_types import InvoiceType
from app.services.pdf_processor import PdfSideData


class PdfExtractResponse(BaseModel):
    """Resultado da extração só-PDF (heurística ± LLM)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "invoice_type": "nfe",
                "issuer": {"name": None, "cnpj": "12345678000199", "cpf": None, "address": None},
                "receiver": {"name": None, "cnpj": "98765432000188", "cpf": None, "address": None},
                "invoice_number": "12345",
                "date": "15/01/2024",
                "total_value": 20.0,
                "liquid_value": None,
                "items": [],
                "taxes_note": None,
                "iss": None,
                "used_llm": False,
                "extraction_mode": "deterministic",
                "quality_score": 0.72,
                "raw_text": "DANFE Nota Fiscal N 12345\n...",
                "warnings": [],
                "llm_extracted": None,
            }
        }
    )

    invoice_type: Literal["nfe", "nfse"] = Field(description="Tipo usado nos prompts/heurísticas.")
    issuer: Party | None = None
    receiver: Party | None = None
    invoice_number: str | None = None
    date: str | None = None
    total_value: float | None = None
    liquid_value: float | None = None
    items: list[LineItem] = Field(default_factory=list)
    taxes_note: str | None = None
    iss: float | None = None
    used_llm: bool = Field(description="Se o LLM foi usado nesta extração PDF.")
    extraction_mode: str = Field(description="`deterministic` ou `llm`.")
    quality_score: float = Field(description="Heurística de qualidade do texto extraído (0–1).")
    raw_text: str = Field(
        description=(
            "Texto extraído do PDF para depuração; truncado ao máximo configurado por "
            "`PDF_RAW_TEXT_MAX_CHARS` (por omissão 100000 caracteres)."
        ),
    )
    warnings: list[str] = Field(default_factory=list)
    llm_extracted: PdfExtractionLLMResponse | None = Field(
        default=None,
        description="JSON estruturado devolvido pelo LLM; preenchido só quando `used_llm` é true.",
    )


def pdf_side_data_to_response(
    data: PdfSideData, *, invoice_type: InvoiceType
) -> PdfExtractResponse:
    return PdfExtractResponse(
        invoice_type=invoice_type,
        issuer=data.issuer,
        receiver=data.receiver,
        invoice_number=data.invoice_number,
        date=data.date,
        total_value=data.total_value,
        liquid_value=data.liquid_value,
        items=data.items,
        taxes_note=data.taxes_note,
        iss=data.iss,
        used_llm=data.used_llm,
        extraction_mode=data.extraction_mode,
        quality_score=data.quality_score,
        raw_text=data.raw_text,
        warnings=data.warnings,
        llm_extracted=data.llm_raw,
    )


def simulated_xml_coverage(simulate_complete: bool) -> dict[str, bool]:
    """Mesmas chaves que `xml_field_coverage` em invoice_merge."""
    v = simulate_complete
    return {
        "issuer": v,
        "receiver": v,
        "invoice_number": v,
        "date": v,
        "total": v,
        "items": v,
    }
