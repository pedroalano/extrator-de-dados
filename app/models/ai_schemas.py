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
    """JSON que o LLM deve retornar para mapear uma estrutura XML desconhecida."""

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


class PdfExtractionLLMResponse(BaseModel):
    issuer_name: str | None = None
    issuer_cnpj: str | None = None
    receiver_name: str | None = None
    receiver_cnpj: str | None = None
    invoice_number: str | None = None
    date: str | None = None
    total_value: float | None = None
    products: list[dict] = Field(default_factory=list)
    taxes_note: str | None = None
