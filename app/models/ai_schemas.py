from pydantic import BaseModel, Field


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
    service_inner: ServiceInnerXPaths = Field(default_factory=ServiceInnerXPaths)


class PdfExtractionLLMResponse(BaseModel):
    issuer_name: str | None = None
    issuer_cnpj: str | None = None
    receiver_name: str | None = None
    receiver_cnpj: str | None = None
    invoice_number: str | None = None
    date: str | None = None
    total_value: float | None = None
    items: list[dict] = Field(default_factory=list)
    taxes_note: str | None = None
    iss: float | None = None
