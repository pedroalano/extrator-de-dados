from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from lxml import etree

from app.db.repositories import XmlMappingRepository
from app.models.ai_schemas import ProductInnerXPaths, XPathDiscoveryLLMResponse
from app.models.domain import Party, ProductLine, TaxesSummary
from app.services.ai_service import AIService, XML_PATH_DISCOVERY_SYSTEM
from app.utils.xml_fingerprint import compute_structure_hash
from app.utils.xml_sample import reduce_xml_for_llm

logger = logging.getLogger(__name__)


def default_nfe_xpath_mapping() -> XPathDiscoveryLLMResponse:
    """Layout NFe comum (infNFe) quando ainda não há cache e LLM indisponível."""
    return XPathDiscoveryLLMResponse(
        issuer="//*[local-name()='emit'][1]",
        receiver="//*[local-name()='dest'][1]",
        invoice_number="//*[local-name()='ide']/*[local-name()='nNF']/text()",
        date="//*[local-name()='ide']/*[local-name()='dhEmi']/text() | //*[local-name()='ide']/*[local-name()='dEmi']/text()",
        total_value="//*[local-name()='ICMSTot']/*[local-name()='vNF']/text() | //*[local-name()='total']/*[local-name()='ICMSTot']/*[local-name()='vNF']/text()",
        products_container="//*[local-name()='det']",
        taxes_root="//*[local-name()='total'][1]",
        product_inner=ProductInnerXPaths(),
    )


@dataclass
class XmlProcessResult:
    issuer: Party
    receiver: Party
    invoice_number: str | None
    date: str | None
    total_value: float | None
    products: list[ProductLine]
    taxes: TaxesSummary
    structure_hash: str
    used_llm: bool


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
    cnpj = _xpath_first_text(node, ".//*[local-name()='CNPJ']/text()")
    cpf = _xpath_first_text(node, ".//*[local-name()='CPF']/text()")
    name = _xpath_first_text(node, ".//*[local-name()='xNome']/text()")
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


def _product_from_node(
    node: etree._Element, inner: ProductInnerXPaths
) -> ProductLine:
    return ProductLine(
        code=_xpath_first_text(node, inner.code),
        description=_xpath_first_text(node, inner.description),
        ncm=_xpath_first_text(node, inner.ncm),
        quantity=_parse_decimal(_xpath_first_text(node, inner.quantity)),
        unit=_xpath_first_text(node, inner.unit),
        unit_value=_parse_decimal(_xpath_first_text(node, inner.unit_value)),
        total_value=_parse_decimal(_xpath_first_text(node, inner.total_value)),
    )


def _extract_with_mapping(
    root: etree._Element, m: XPathDiscoveryLLMResponse
) -> XmlProcessResult:
    issuer_n = _xpath_first_element(root, m.issuer)
    receiver_n = _xpath_first_element(root, m.receiver)
    products_nodes = root.xpath(m.products_container)
    if not isinstance(products_nodes, list):
        products_nodes = []

    products: list[ProductLine] = []
    for pn in products_nodes:
        if isinstance(pn, etree._Element):
            products.append(_product_from_node(pn, m.product_inner))

    taxes_n = _xpath_first_element(root, m.taxes_root)
    taxes = _taxes_from_total_node(taxes_n)

    return XmlProcessResult(
        issuer=_party_from_node(issuer_n),
        receiver=_party_from_node(receiver_n),
        invoice_number=_xpath_first_text(root, m.invoice_number),
        date=_xpath_first_text(root, m.date),
        total_value=_parse_decimal(_xpath_first_text(root, m.total_value)),
        products=products,
        taxes=taxes,
        structure_hash="",
        used_llm=False,
    )


class XmlProcessor:
    def __init__(
        self,
        repo: XmlMappingRepository,
        ai: AIService,
    ) -> None:
        self._repo = repo
        self._ai = ai

    async def process(self, xml_bytes: bytes, *, has_api_key: bool) -> XmlProcessResult:
        structure_hash = compute_structure_hash(xml_bytes)
        root = etree.fromstring(xml_bytes)

        used_llm = False
        mapping: XPathDiscoveryLLMResponse | None = None

        doc = await self._repo.find_by_hash(structure_hash)
        if doc and doc.get("xpath_mappings"):
            try:
                mapping = XPathDiscoveryLLMResponse.model_validate(doc["xpath_mappings"])
            except Exception as e:
                logger.warning("Cache de mapping inválido, refazendo: %s", e)
                mapping = None

        if mapping is None:
            if has_api_key:
                sample = reduce_xml_for_llm(
                    xml_bytes, max_chars=min(18000, 24000)
                )
                user = f"XML (amostra):\n```xml\n{sample}\n```"
                try:
                    mapping = await self._ai.complete_json(
                        system_prompt=XML_PATH_DISCOVERY_SYSTEM,
                        user_prompt=user,
                        response_model=XPathDiscoveryLLMResponse,
                        max_tokens=2048,
                    )
                    used_llm = True
                    await self._repo.upsert_mapping(structure_hash, mapping)
                except Exception as e:
                    logger.warning("Falha no LLM para XPaths, usando fallback: %s", e)
                    mapping = default_nfe_xpath_mapping()
            else:
                mapping = default_nfe_xpath_mapping()

        result = _extract_with_mapping(root, mapping)
        result.structure_hash = structure_hash
        result.used_llm = used_llm
        return result
