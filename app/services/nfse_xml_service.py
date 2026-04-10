"""Extração XML para NFS-e (serviços)."""

from __future__ import annotations

import logging

from lxml import etree

from app.db.repositories import XmlMappingRepository
from app.models.ai_schemas import NfseXPathMapping
from app.services.ai_service import AIService
from app.services.prompts import XML_PATH_DISCOVERY_NFSE
from app.services.xml_extract_common import (
    XmlProcessResult,
    _line_from_service_inner,
    _parse_decimal,
    _party_from_node,
    _xpath_first_element,
    _xpath_first_text,
)
from app.models.domain import TaxesSummary
from app.utils.xml_fingerprint import compute_structure_hash
from app.utils.xml_sample import reduce_xml_for_llm

logger = logging.getLogger(__name__)


def default_nfse_xpath_mapping() -> NfseXPathMapping:
    return NfseXPathMapping()


def _iss_from_mapping(
    root: etree._Element, m: NfseXPathMapping
) -> tuple[float | None, dict[str, str]]:
    raw: dict[str, str] = {}
    taxes_n = _xpath_first_element(root, m.taxes_root)
    iss_val: float | None = None
    expr = m.iss_total.strip()
    if expr.startswith("//") or expr.startswith("/"):
        t = _xpath_first_text(root, expr)
        if t is not None:
            raw["iss"] = t
        iss_val = _parse_decimal(t)
    else:
        base = taxes_n if taxes_n is not None else root
        t = _xpath_first_text(base, expr)
        if t is not None:
            raw["iss"] = t
        iss_val = _parse_decimal(t)
    return iss_val, raw


def extract_nfse_with_mapping(root: etree._Element, m: NfseXPathMapping) -> XmlProcessResult:
    prestador_n = _xpath_first_element(root, m.prestador)
    tomador_n = _xpath_first_element(root, m.tomador)
    item_nodes = root.xpath(m.services_container)
    if not isinstance(item_nodes, list):
        item_nodes = []

    items: list = []
    for pn in item_nodes:
        if isinstance(pn, etree._Element):
            items.append(_line_from_service_inner(pn, m.service_inner))

    iss_val, raw_tax = _iss_from_mapping(root, m)

    return XmlProcessResult(
        invoice_type="nfse",
        issuer=_party_from_node(prestador_n),
        receiver=_party_from_node(tomador_n),
        invoice_number=_xpath_first_text(root, m.invoice_number),
        date=_xpath_first_text(root, m.date),
        total_value=_parse_decimal(_xpath_first_text(root, m.total_value)),
        items=items,
        taxes=TaxesSummary(iss=iss_val, raw=raw_tax),
        structure_hash="",
        used_llm=False,
    )


async def process_nfse_xml(
    xml_bytes: bytes,
    *,
    has_api_key: bool,
    repo: XmlMappingRepository,
    ai: AIService,
) -> XmlProcessResult:
    structure_hash = compute_structure_hash(xml_bytes, "nfse")
    root = etree.fromstring(xml_bytes)

    used_llm = False
    mapping_source = "default"
    mapping: NfseXPathMapping | None = None

    doc = await repo.find_by_hash(structure_hash, "nfse")
    if doc and doc.get("xpath_mappings"):
        try:
            mapping = NfseXPathMapping.model_validate(doc["xpath_mappings"])
            mapping_source = "cached"
        except Exception as e:
            logger.warning("Cache de mapping NFS-e inválido, refazendo: %s", e)
            mapping = None

    if mapping is None:
        if has_api_key:
            sample = reduce_xml_for_llm(xml_bytes, max_chars=min(18000, 24000))
            user = f"XML (amostra):\n```xml\n{sample}\n```"
            try:
                mapping = await ai.complete_json(
                    system_prompt=XML_PATH_DISCOVERY_NFSE,
                    user_prompt=user,
                    response_model=NfseXPathMapping,
                    max_tokens=2048,
                )
                used_llm = True
                mapping_source = "llm"
                await repo.upsert_mapping(structure_hash, "nfse", mapping)
            except Exception as e:
                logger.warning("Falha no LLM para XPaths NFS-e, usando fallback: %s", e)
                mapping = default_nfse_xpath_mapping()
        else:
            mapping = default_nfse_xpath_mapping()

    result = extract_nfse_with_mapping(root, mapping)
    result.structure_hash = structure_hash
    result.used_llm = used_llm
    result.mapping_source = mapping_source
    return result
