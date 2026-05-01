"""Heurística determinística do número da NFS-e no texto do PDF."""

from __future__ import annotations

from app.services.pdf_processor import (
    _deterministic_from_text,
    _nfse_invoice_number_from_text,
)


def test_nfse_number_prefers_label_over_address_digits():
    text = """
    PREFEITURA Nota Fiscal de Serviços Eletrônica
    VISCONDE DE TAUNAY, 950 - 84051900 - RONDA - PONTA GROSSA - PR
    SECRETARIA MUNICIPAL DA FAZENDA     Número:
                                                    46466
    Emissão: 10/10/2025
    """
    assert _nfse_invoice_number_from_text(text) == "46466"


def test_nfse_number_nfs_e_footer():
    text = """
    Nota Fiscal de Serviços
    TOTALIZAÇÃO DO DOCUMENTO FISCAL
    NFS-E Nº   46466
    """
    assert _nfse_invoice_number_from_text(text) == "46466"


def test_deterministic_nfse_uses_heuristic():
    sample = """
    Nota Fiscal de Serviços
    VISCONDE - 84051900 -
    Número:
    46466
    """
    side = _deterministic_from_text(sample, "nfse")
    assert side.invoice_number == "46466"
