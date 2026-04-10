import hashlib

from lxml import etree

from app.models.invoice_types import InvoiceType


def compute_structure_hash(xml_bytes: bytes, invoice_type: InvoiceType) -> str:
    """Fingerprint estrutural (tags e profundidade, sem texto), prefixado pelo tipo."""
    root = etree.fromstring(xml_bytes)
    parts: list[str] = []

    def walk(element: etree._Element, depth: int) -> None:
        tag = etree.QName(element).localname
        parts.append(f"{depth}:{tag}")
        for child in element:
            walk(child, depth + 1)

    walk(root, 0)

    versao = ""
    if invoice_type == "nfe":
        versao_nodes = root.xpath("//*[local-name()='infNFe']/@versao")
        versao = versao_nodes[0] if versao_nodes else ""
    else:
        for attr in ("versao", "Versao", "version"):
            vnodes = root.xpath(f"//*[local-name()='InfNfse']/@{attr}")
            if vnodes:
                versao = str(vnodes[0])
                break
            vnodes = root.xpath(f"//*[local-name()='Nfse']/@{attr}")
            if vnodes:
                versao = str(vnodes[0])
                break

    payload = f"{invoice_type}|{versao}|" + "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
