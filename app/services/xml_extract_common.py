"""Utilitários compartilhados para extração XML (NFe e NFS-e)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from lxml import etree

from app.models.domain import LineItem, Party, TaxesSummary
from app.models.invoice_types import InvoiceType

logger = logging.getLogger(__name__)


@dataclass
class XmlProcessResult:
    invoice_type: InvoiceType
    issuer: Party
    receiver: Party
    invoice_number: str | None
    date: str | None
    total_value: float | None
    items: list[LineItem]
    taxes: TaxesSummary
    structure_hash: str
    used_llm: bool
    mapping_source: str = "default"  # cached | llm | default


def _xpath_first_text(root: etree._Element, xpath_expr: str) -> str | None:
    try:
        r = root.xpath(xpath_expr)
    except etree.XPathEvalError as e:
        logger.warning("XPath inválido %s: %s", xpath_expr, e)
        return None
    if not r:
        return None
    el = r[0]
    if isinstance(el, str):
        s = el.strip()
        return s or None
    if isinstance(el, etree._Element):
        t = (el.text or "").strip()
        if t:
            return t
        return "".join(el.itertext()).strip() or None
    return str(el).strip() or None


def _xpath_first_element(root: etree._Element, xpath_expr: str) -> etree._Element | None:
    try:
        r = root.xpath(xpath_expr)
    except etree.XPathEvalError as e:
        logger.warning("XPath elemento inválido %s: %s", xpath_expr, e)
        return None
    if not r:
        return None
    el = r[0]
    if isinstance(el, etree._Element):
        return el
    return None


def _parse_decimal(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    s = str(value).strip().replace(" ", "")
    if re.match(r"^\d+,\d+$", s):
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _party_from_node(node: etree._Element | None) -> Party:
    if node is None:
        return Party()
    cnpj = None
    for tag in ("CNPJ", "Cnpj", "cnpj"):
        cnpj = _xpath_first_text(node, f".//*[local-name()='{tag}']/text()")
        if cnpj:
            break
    cpf = None
    for tag in ("CPF", "Cpf", "cpf"):
        cpf = _xpath_first_text(node, f".//*[local-name()='{tag}']/text()")
        if cpf:
            break
    name = _xpath_first_text(node, ".//*[local-name()='xNome']/text()")
    if not name:
        name = _xpath_first_text(node, ".//*[local-name()='RazaoSocial']/text()")
    if not name:
        name = _xpath_first_text(node, ".//*[local-name()='Nome']/text()")
    parts = []
    for tag in ("xLgr", "nro", "xBairro", "xMun", "UF", "CEP"):
        t = _xpath_first_text(node, f".//*[local-name()='{tag}']/text()")
        if t:
            parts.append(t)
    address = ", ".join(parts) if parts else None
    return Party(name=name, cnpj=cnpj, cpf=cpf, address=address)


def _taxes_from_total_node(node: etree._Element | None) -> TaxesSummary:
    if node is None:
        return TaxesSummary()
    raw: dict[str, Any] = {}

    def grab(tag: str) -> str | None:
        return _xpath_first_text(node, f".//*[local-name()='{tag}']/text()")

    for tag in (
        "vBC",
        "vICMS",
        "vICMSDeson",
        "vFCP",
        "vBCST",
        "vST",
        "vFCPST",
        "vFCPSTRet",
        "vProd",
        "vFrete",
        "vSeg",
        "vDesc",
        "vII",
        "vIPI",
        "vIPIDevol",
        "vPIS",
        "vCOFINS",
        "vOutro",
        "vNF",
    ):
        val = grab(tag)
        if val is not None:
            raw[tag] = val

    return TaxesSummary(
        icms=_parse_decimal(grab("vICMS")),
        ipi=_parse_decimal(grab("vIPI")),
        pis=_parse_decimal(grab("vPIS")),
        cofins=_parse_decimal(grab("vCOFINS")),
        total_taxes=None,
        raw=raw,
    )


def _line_from_product_inner(
    node: etree._Element, inner: Any
) -> LineItem:
    from app.models.ai_schemas import ProductInnerXPaths

    if not isinstance(inner, ProductInnerXPaths):
        inner = ProductInnerXPaths.model_validate(inner)
    return LineItem(
        code=_xpath_first_text(node, inner.code),
        description=_xpath_first_text(node, inner.description),
        ncm=_xpath_first_text(node, inner.ncm),
        quantity=_parse_decimal(_xpath_first_text(node, inner.quantity)),
        unit=_xpath_first_text(node, inner.unit),
        unit_value=_parse_decimal(_xpath_first_text(node, inner.unit_value)),
        total_value=_parse_decimal(_xpath_first_text(node, inner.total_value)),
    )


def _line_from_service_inner(node: etree._Element, inner: Any) -> LineItem:
    from app.models.ai_schemas import ServiceInnerXPaths

    if not isinstance(inner, ServiceInnerXPaths):
        inner = ServiceInnerXPaths.model_validate(inner)
    return LineItem(
        code=_xpath_first_text(node, inner.code),
        description=_xpath_first_text(node, inner.description),
        ncm=None,
        quantity=_parse_decimal(_xpath_first_text(node, inner.quantity)),
        unit=_xpath_first_text(node, inner.unit),
        unit_value=_parse_decimal(_xpath_first_text(node, inner.unit_value)),
        total_value=_parse_decimal(_xpath_first_text(node, inner.total_value)),
    )
