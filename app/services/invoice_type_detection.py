"""Heurísticas para classificar XML como NFe (produto) ou NFS-e (serviço)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from lxml import etree

from app.models.invoice_types import InvoiceType

logger = logging.getLogger(__name__)

NFE_NS = "http://www.portalfiscal.inf.br/nfe"

# Padrões comuns em NFS-e (ABRASF e variações municipais)
NFSE_ROOT_HINTS = frozenset(
    {
        "compnfse",
        "nfse",
        "infnfse",
        "listanfse",
        "gerarnfseresponse",
        "consultarnfseresponse",
    }
)
NFSE_DESCENDANT_HINTS = frozenset(
    {
        "prestadorservico",
        "tomadorservico",
        "identificacaonfse",
        "valornfse",
        "valorservicos",
        "valordeducoes",
        "valorpis",
        "valorcofins",
        "valoinss",
        "valorir",
        "valorcsll",
        "valortotalretencoes",
        "valoliquidonfse",
        "valorcredito",
        "servico",
        "discriminacao",
    }
)


@dataclass
class InvoiceTypeDetection:
    invoice_type: InvoiceType
    signals: list[str] = field(default_factory=list)


def _doc_namespace_hints(root: etree._Element) -> list[str]:
    hints: list[str] = []
    ns = root.nsmap or {}
    for u in ns.values():
        if not u:
            continue
        u_low = u.lower()
        if "portalfiscal" in u_low and "nfe" in u_low:
            hints.append("ns_nfe_portalfiscal")
        if "nfse" in u_low or "iss" in u_low or "abrasf" in u_low:
            hints.append("ns_nfse_like")
    return hints


def _collect_local_names(root: etree._Element, max_nodes: int = 400) -> set[str]:
    names: set[str] = set()
    count = 0
    for el in root.iter():
        if count >= max_nodes:
            break
        tag = etree.QName(el).localname
        names.add(tag.lower())
        count += 1
    return names


def detect_invoice_type(xml_bytes: bytes) -> InvoiceTypeDetection:
    """Classifica o documento XML. Em caso de empate, prioriza NFe se houver infNFe."""
    root = etree.fromstring(xml_bytes)
    root_local = etree.QName(root).localname.lower()
    ns_hints = _doc_namespace_hints(root)
    names = _collect_local_names(root)
    signals: list[str] = []

    if NFE_NS in (root.nsmap or {}).values() or any(
        "portalfiscal" in (u or "").lower() and "nfe" in (u or "").lower()
        for u in (root.nsmap or {}).values()
    ):
        signals.append("namespace_nfe")

    if "nfeproc" in names or "infnfe" in names or "nfe" in names:
        signals.append("tags_nfe")
    if "infse" in names or "infnfse" in names:
        signals.append("tags_inf_nfse")

    for h in NFSE_ROOT_HINTS:
        if h in root_local or h in names:
            signals.append(f"nfse_hint_{h}")
            break

    for h in NFSE_DESCENDANT_HINTS:
        if h in names:
            signals.append("nfse_descendant")
            break

    for h in ns_hints:
        signals.append(h)

    # Decisão
    is_nfe = (
        "infNFe".lower() in names
        or "nfe" in names and "infnfe" in names
        or ("tags_nfe" in signals and "nfse_descendant" not in signals)
        or "namespace_nfe" in signals
    )
    is_nfse = (
        "nfse_descendant" in signals
        or any(s.startswith("nfse_hint_") for s in signals)
        or "tags_inf_nfse" in signals
        or ("infnfse" in names or "compnfse" in names)
        or ("ns_nfse_like" in signals and "tags_nfe" not in signals)
    )

    if is_nfe and not is_nfse:
        return InvoiceTypeDetection("nfe", signals)
    if is_nfse and not is_nfe:
        return InvoiceTypeDetection("nfse", signals)
    if is_nfe and is_nfse:
        # Conflito raro: priorizar NFe se infNFe presente
        if "infNFe".lower() in names or "infnfe" in names:
            logger.warning("Detecção ambígua; priorizando NFe (infNFe presente)")
            return InvoiceTypeDetection("nfe", signals + ["ambiguous_chose_nfe"])
        logger.warning("Detecção ambígua; priorizando NFS-e")
        return InvoiceTypeDetection("nfse", signals + ["ambiguous_chose_nfse"])

    # Fallback: raiz típica
    if root_local in ("nfeproc", "nfe"):
        return InvoiceTypeDetection("nfe", signals + ["fallback_root"])
    if root_local in NFSE_ROOT_HINTS or "nfse" in root_local:
        return InvoiceTypeDetection("nfse", signals + ["fallback_root"])

    # Padrão conservador: NFe (compatibilidade com fluxo legado)
    return InvoiceTypeDetection("nfe", signals + ["fallback_default_nfe"])
