from lxml import etree

from app.models.ai_schemas import XPathDiscoveryLLMResponse
from app.services.xml_processor import _extract_with_mapping, default_nfe_xpath_mapping


def test_extract_with_default_mapping(minimal_nfe_xml: bytes):
    root = etree.fromstring(minimal_nfe_xml)
    m = default_nfe_xpath_mapping()
    r = _extract_with_mapping(root, m)
    r.structure_hash = "test"
    assert r.invoice_number == "12345"
    assert r.issuer.cnpj == "12345678000199"
    assert r.issuer.name == "Empresa Emitente LTDA"
    assert r.receiver.cnpj == "98765432000188"
    assert r.total_value == 20.0
    assert len(r.products) == 1
    assert r.products[0].code == "001"
    assert r.products[0].description == "Produto Teste"
    assert r.taxes.icms == 3.0


def test_extract_respects_custom_xpath(minimal_nfe_xml: bytes):
    root = etree.fromstring(minimal_nfe_xml)
    m = XPathDiscoveryLLMResponse(
        issuer="//*[local-name()='emit'][1]",
        receiver="//*[local-name()='dest'][1]",
        invoice_number="//*[local-name()='nNF']/text()",
        date="//*[local-name()='dhEmi']/text()",
        total_value="//*[local-name()='vNF']/text()",
        products_container="//*[local-name()='det']",
        taxes_root="//*[local-name()='total'][1]",
    )
    r = _extract_with_mapping(root, m)
    assert r.invoice_number == "12345"
    assert r.total_value == 20.0
