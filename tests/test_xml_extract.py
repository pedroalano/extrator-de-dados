from lxml import etree

from app.models.ai_schemas import XPathDiscoveryLLMResponse
from app.services.invoice_type_detection import detect_invoice_type
from app.services.nfe_xml_service import (
    default_nfe_xpath_mapping,
    extract_nfe_with_mapping,
)
from app.services.nfse_xml_service import (
    default_nfse_xpath_mapping,
    extract_nfse_with_mapping,
)


def test_extract_with_default_mapping(minimal_nfe_xml: bytes):
    root = etree.fromstring(minimal_nfe_xml)
    m = default_nfe_xpath_mapping()
    r = extract_nfe_with_mapping(root, m)
    r.structure_hash = "test"
    assert r.invoice_number == "12345"
    assert r.issuer.cnpj == "12345678000199"
    assert r.issuer.name == "Empresa Emitente LTDA"
    assert r.receiver.cnpj == "98765432000188"
    assert r.total_value == 20.0
    assert len(r.items) == 1
    assert r.items[0].code == "001"
    assert r.items[0].description == "Produto Teste"
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
    r = extract_nfe_with_mapping(root, m)
    assert r.invoice_number == "12345"
    assert r.total_value == 20.0


def test_detect_nfse_fixture(minimal_nfse_xml: bytes):
    d = detect_invoice_type(minimal_nfse_xml)
    assert d.invoice_type == "nfse"


def test_extract_nfse_default_mapping(minimal_nfse_xml: bytes):
    root = etree.fromstring(minimal_nfse_xml)
    m = default_nfse_xpath_mapping()
    r = extract_nfse_with_mapping(root, m)
    assert r.invoice_number == "888888"
    assert r.issuer.cnpj == "11111111000111"
    assert r.receiver.cnpj == "22222222000122"
    assert r.total_value == 150.0
    assert r.taxes.iss == 3.0
    assert len(r.items) == 1
    assert r.items[0].description == "Consultoria tecnica"
