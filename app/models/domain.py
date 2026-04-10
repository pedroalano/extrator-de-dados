from typing import Any, Literal

from pydantic import BaseModel, Field


class Party(BaseModel):
    name: str | None = None
    cnpj: str | None = None
    cpf: str | None = None
    address: str | None = None


class LineItem(BaseModel):
    """Linha de produto (NFe) ou serviço (NFS-e)."""

    code: str | None = None
    description: str | None = None
    ncm: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_value: float | None = None
    total_value: float | None = None


# Alias legado (código interno / imports antigos)
ProductLine = LineItem


class TaxesSummary(BaseModel):
    icms: float | None = None
    ipi: float | None = None
    iss: float | None = None
    pis: float | None = None
    cofins: float | None = None
    total_taxes: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class InvoiceProcessResponse(BaseModel):
    invoice_type: Literal["nfe", "nfse"]
    issuer: Party
    receiver: Party
    total_value: float | None = None
    items: list[LineItem] = Field(default_factory=list)
    taxes: TaxesSummary
    date: str | None = None
    invoice_number: str | None = None

    structure_hash: str | None = None
    used_llm_xml: bool = False
    used_llm_pdf: bool = False
    warnings: list[str] = Field(default_factory=list)

    field_confidence: dict[str, float] | None = None
    extraction_sources: dict[str, str] | None = None
