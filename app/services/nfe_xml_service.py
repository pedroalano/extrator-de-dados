"""Extração XML para NFe (produtos)."""

from __future__ import annotations

import logging

from lxml import etree

from app.db.repositories import XmlMappingRepository
from app.models.ai_schemas import ProductInnerXPaths, XPathDiscoveryLLMResponse
from app.services.ai_service import AIService
from app.services.prompts import XML_PATH_DISCOVERY_NFE
from app.services.xml_extract_common import (
    XmlProcessResult,
    _line_from_product_inner,
    _parse_decimal,
    _party_from_node,
    _taxes_from_total_node,
    _xpath_first_element,
    _xpath_first_text,
)
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
        liquid_value="",
        products_container="//*[local-name()='det']",
        taxes_root="//*[local-name()='total'][1]",
        product_inner=ProductInnerXPaths(),
    )


def extract_nfe_with_mapping(
    root: etree._Element, m: XPathDiscoveryLLMResponse
) -> XmlProcessResult:
    issuer_n = _xpath_first_element(root, m.issuer)
    receiver_n = _xpath_first_element(root, m.receiver)
    item_nodes = root.xpath(m.products_container)
    if not isinstance(item_nodes, list):
        item_nodes = []

    items: list = []
    for pn in item_nodes:
        if isinstance(pn, etree._Element):
            items.append(_line_from_product_inner(pn, m.product_inner))

    taxes_n = _xpath_first_element(root, m.taxes_root)
    taxes = _taxes_from_total_node(taxes_n)

    lv_expr = (m.liquid_value or "").strip()
    liquid_value = (
        _parse_decimal(_xpath_first_text(root, lv_expr)) if lv_expr else None
    )

    return XmlProcessResult(
        invoice_type="nfe",
        issuer=_party_from_node(issuer_n),
        receiver=_party_from_node(receiver_n),
        invoice_number=_xpath_first_text(root, m.invoice_number),
        date=_xpath_first_text(root, m.date),
        total_value=_parse_decimal(_xpath_first_text(root, m.total_value)),
        items=items,
        taxes=taxes,
        structure_hash="",
        used_llm=False,
        liquid_value=liquid_value,
    )


async def process_nfe_xml(
    xml_bytes: bytes,
    *,
    has_api_key: bool,
    repo: XmlMappingRepository,
    ai: AIService,
) -> XmlProcessResult:
    structure_hash = compute_structure_hash(xml_bytes, "nfe")
    root = etree.fromstring(xml_bytes)

    used_llm = False
    mapping_source = "default"
    mapping: XPathDiscoveryLLMResponse | None = None

    doc = await repo.find_by_hash(structure_hash, "nfe")
    if doc and doc.get("xpath_mappings"):
        try:
            mapping = XPathDiscoveryLLMResponse.model_validate(doc["xpath_mappings"])
            mapping_source = "cached"
        except Exception as e:
            logger.warning("Cache de mapping NFe inválido, refazendo: %s", e)
            mapping = None

    if mapping is None:
        if has_api_key:
            sample = reduce_xml_for_llm(xml_bytes, max_chars=min(18000, 24000))
            user = f"XML (amostra):\n```xml\n{sample}\n```"
            try:
                mapping = await ai.complete_json(
                    system_prompt=XML_PATH_DISCOVERY_NFE,
                    user_prompt=user,
                    response_model=XPathDiscoveryLLMResponse,
                    max_tokens=2048,
                )
                used_llm = True
                mapping_source = "llm"
                await repo.upsert_mapping(structure_hash, "nfe", mapping)
            except Exception as e:
                logger.warning("Falha no LLM para XPaths NFe, usando fallback: %s", e)
                mapping = default_nfe_xpath_mapping()
        else:
            mapping = default_nfe_xpath_mapping()

    result = extract_nfe_with_mapping(root, mapping)
    result.structure_hash = structure_hash
    result.used_llm = used_llm
    result.mapping_source = mapping_source
    return result
