from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProductInnerXPaths(BaseModel):
    code: str = Field(default=".//*[local-name()='cProd']/text()")
    description: str = Field(default=".//*[local-name()='xProd']/text()")
    ncm: str = Field(default=".//*[local-name()='NCM']/text()")
    quantity: str = Field(default=".//*[local-name()='qCom']/text()")
    unit: str = Field(default=".//*[local-name()='uCom']/text()")
    unit_value: str = Field(default=".//*[local-name()='vUnCom']/text()")
    total_value: str = Field(default=".//*[local-name()='vProd']/text()")


class XPathDiscoveryLLMResponse(BaseModel):
    """Mapeamento XPath para NFe (produto)."""

    issuer: str = Field(
        description="XPath absoluto ao emit (ex.: //*[local-name()='emit'][1])"
    )
    receiver: str = Field(description="XPath absoluto ao dest")
    invoice_number: str = Field(description="XPath ao texto nNF")
    date: str = Field(description="XPath ao texto dhEmi ou dEmi")
    total_value: str = Field(description="XPath ao texto vNF")
    liquid_value: str = Field(
        default="",
        description="XPath opcional ao valor líquido da NF se existir tag dedicada; vazio = omitir",
    )
    products_container: str = Field(
        description="XPath que retorna cada nó de item (det)"
    )
    taxes_root: str = Field(description="XPath ao bloco total / impostos")
    product_inner: ProductInnerXPaths = Field(default_factory=ProductInnerXPaths)


class ServiceInnerXPaths(BaseModel):
    code: str = Field(default=".//*[local-name()='ItemListaServico']/text()")
    description: str = Field(
        default=".//*[local-name()='Discriminacao']/text()"
    )
    quantity: str = Field(default=".//*[local-name()='Quantidade']/text()")
    unit: str = Field(default=".//*[local-name()='Unidade']/text()")
    unit_value: str = Field(default=".//*[local-name()='ValorUnitario']/text()")
    total_value: str = Field(
        default=".//*[local-name()='Valores']/*[local-name()='ValorServicos']/text()"
    )


class NfseXPathMapping(BaseModel):
    """Mapeamento XPath para NFS-e (prestador/tomador/serviços)."""

    prestador: str = Field(
        default="//*[local-name()='PrestadorServico'][1]",
        description="XPath ao bloco do prestador",
    )
    tomador: str = Field(
        default="//*[local-name()='TomadorServico'][1]",
        description="XPath ao bloco do tomador",
    )
    invoice_number: str = Field(
        default="//*[local-name()='InfNfse']/*[local-name()='Numero']/text()",
        description="Número da NFS-e",
    )
    date: str = Field(
        default=(
            "//*[local-name()='InfNfse']/*[local-name()='DataEmissao']/text() | "
            "//*[local-name()='DataEmissao']/text()"
        ),
        description="Data de emissão ou competência",
    )
    total_value: str = Field(
        default=(
            "//*[local-name()='Servico']//*[local-name()='Valores']"
            "/*[local-name()='ValorServicos']/text()"
        ),
        description="Valor total dos serviços",
    )
    services_container: str = Field(
        default="//*[local-name()='Servico']",
        description="XPath que retorna cada item de serviço",
    )
    taxes_root: str = Field(
        default="//*[local-name()='Servico']//*[local-name()='Valores'][1]",
        description="Bloco de valores/tributos do serviço",
    )
    iss_total: str = Field(
        default=".//*[local-name()='ValorIss']/text()",
        description="XPath (preferencialmente relativo a taxes_root) ao ISS",
    )
    liquid_value: str = Field(
        default="",
        description="XPath opcional ao valor líquido da NFS-e (ex. ValorLiquido); vazio = omitir",
    )
    service_inner: ServiceInnerXPaths = Field(default_factory=ServiceInnerXPaths)


class PdfDocumentInfo(BaseModel):
    """Metadados da nota (bloco document_info no JSON do modelo)."""

    model_config = ConfigDict(extra="ignore")

    document_kind: Literal["nfe", "nfse"] | None = Field(
        default=None,
        description="nfe = NF-e/DANFE (mercadoria); nfse = NFS-e (serviço).",
    )
    invoice_number: str | None = None
    date: str | None = Field(
        default=None, description="Data em ISO-8601 (YYYY-MM-DD) quando identificável."
    )


class PdfPartyExtract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    cnpj: str | None = None
    cpf: str | None = None
    address: str | None = None


class PdfItemTaxExtract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    icms: float | None = None
    iss: float | None = None


class PdfLineExtract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None
    code: str | None = None
    unit: str | None = None
    ncm: str | None = None
    taxes: PdfItemTaxExtract | None = None


class PdfTaxesExtract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    note: str | None = Field(
        default=None,
        description="Texto livre sobre tributos quando não estruturável.",
    )
    iss: float | None = None
    icms: float | None = None
    pis: float | None = None
    cofins: float | None = None
    ipi: float | None = None


class PdfTotalsExtract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_value: float | None = None
    liquid_value: float | None = Field(
        default=None,
        description="Valor líquido da nota quando distinto do total bruto (ex. NFS-e após retenções).",
    )


class PdfExtractionLLMResponse(BaseModel):
    """Resposta estruturada do LLM na extração por PDF (Master Prompt)."""

    model_config = ConfigDict(extra="ignore")

    document_info: PdfDocumentInfo | None = None
    issuer: PdfPartyExtract | None = None
    receiver: PdfPartyExtract | None = None
    items: list[PdfLineExtract] = Field(default_factory=list)
    taxes: PdfTaxesExtract | dict[str, Any] | None = None
    totals: PdfTotalsExtract | None = None
