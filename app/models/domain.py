from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HTTPErrorResponse(BaseModel):
    """Corpo padrão de erro da API (`HTTPException` / validação FastAPI)."""

    detail: str | list[Any] = Field(
        ...,
        description="Mensagem de erro ou, em 422, lista de erros de validação.",
    )


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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "invoice_type": "nfe",
                "issuer": {
                    "name": "Emitente Exemplo SA",
                    "cnpj": "12345678000199",
                    "cpf": None,
                    "address": "Rua A, 1 — São Paulo/SP",
                },
                "receiver": {
                    "name": "Destinatário Ltda",
                    "cnpj": "98765432000188",
                    "cpf": None,
                    "address": "Av. B, 100",
                },
                "total_value": 20.0,
                "items": [
                    {
                        "code": "001",
                        "description": "Produto exemplo",
                        "ncm": "12345678",
                        "quantity": 1.0,
                        "unit": "UN",
                        "unit_value": 20.0,
                        "total_value": 20.0,
                    }
                ],
                "taxes": {
                    "icms": 2.0,
                    "ipi": None,
                    "iss": None,
                    "pis": 0.13,
                    "cofins": 0.6,
                    "total_taxes": None,
                    "raw": {},
                },
                "date": "2024-01-15",
                "invoice_number": "12345",
                "structure_hash": "abc123def456",
                "used_llm_xml": False,
                "used_llm_pdf": False,
                "warnings": [],
                "field_confidence": None,
                "extraction_sources": {
                    "xml_mapping": "default",
                    "pdf": "deterministic",
                },
            }
        }
    )

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
