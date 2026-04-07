import hashlib

from lxml import etree


def compute_structure_hash(xml_bytes: bytes) -> str:
    """Fingerprint estrutural (tags e profundidade, sem texto)."""
    root = etree.fromstring(xml_bytes)
    parts: list[str] = []

    def walk(element: etree._Element, depth: int) -> None:
        tag = etree.QName(element).localname
        parts.append(f"{depth}:{tag}")
        for child in element:
            walk(child, depth + 1)

    walk(root, 0)

    versao_nodes = root.xpath("//*[local-name()='infNFe']/@versao")
    versao = versao_nodes[0] if versao_nodes else ""

    payload = versao + "|" + "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
