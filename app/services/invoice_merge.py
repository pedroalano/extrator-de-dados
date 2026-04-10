from __future__ import annotations

from app.models.domain import InvoiceProcessResponse, LineItem, Party, TaxesSummary
from app.models.invoice_types import InvoiceType
from app.services.pdf_processor import PdfSideData
from app.services.xml_extract_common import XmlProcessResult


def _merge_party(xml_p: Party, pdf_p: Party | None) -> Party:
    if pdf_p is None:
        return xml_p

    def pick(a: str | None, b: str | None) -> str | None:
        return (a if (a and str(a).strip()) else None) or (
            b if (b and str(b).strip()) else None
        )

    return Party(
        name=pick(xml_p.name, pdf_p.name),
        cnpj=pick(xml_p.cnpj, pdf_p.cnpj),
        cpf=pick(xml_p.cpf, pdf_p.cpf),
        address=pick(xml_p.address, pdf_p.address),
    )


def _merge_items(
    xml_list: list[LineItem], pdf_list: list[LineItem]
) -> list[LineItem]:
    if xml_list:
        return xml_list
    return pdf_list


def _merge_taxes(
    xml_t: TaxesSummary, pdf_note: str | None, pdf_iss: float | None
) -> TaxesSummary:
    out = xml_t.model_copy(deep=True)
    if pdf_iss is not None and out.iss is None:
        out.iss = pdf_iss
    return out


def merge_invoice(
    xml_part: XmlProcessResult,
    pdf_part: PdfSideData,
    *,
    invoice_type: InvoiceType,
) -> InvoiceProcessResponse:
    warnings: list[str] = list(pdf_part.warnings)

    issuer = _merge_party(xml_part.issuer, pdf_part.issuer)
    receiver = _merge_party(xml_part.receiver, pdf_part.receiver)

    invoice_number = xml_part.invoice_number or pdf_part.invoice_number
    date = xml_part.date or pdf_part.date
    total_value = (
        xml_part.total_value
        if xml_part.total_value is not None
        else pdf_part.total_value
    )

    items = _merge_items(xml_part.items, pdf_part.items)

    taxes = _merge_taxes(xml_part.taxes, pdf_part.taxes_note, pdf_part.iss)
    if pdf_part.taxes_note and not xml_part.taxes.raw:
        warnings.append(f"pdf_taxes_note: {pdf_part.taxes_note}")

    extraction_sources: dict[str, str] = {
        "xml_mapping": xml_part.mapping_source,
        "pdf": pdf_part.extraction_mode,
    }

    return InvoiceProcessResponse(
        invoice_type=invoice_type,
        issuer=issuer,
        receiver=receiver,
        total_value=total_value,
        items=items,
        taxes=taxes if isinstance(taxes, TaxesSummary) else TaxesSummary(),
        date=date,
        invoice_number=invoice_number,
        structure_hash=xml_part.structure_hash,
        used_llm_xml=xml_part.used_llm,
        used_llm_pdf=pdf_part.used_llm,
        warnings=warnings,
        extraction_sources=extraction_sources,
        field_confidence=None,
    )


def xml_field_coverage(x: XmlProcessResult) -> dict[str, bool]:
    return {
        "issuer": bool(x.issuer.cnpj or x.issuer.cpf or x.issuer.name),
        "receiver": bool(x.receiver.cnpj or x.receiver.cpf or x.receiver.name),
        "invoice_number": bool(x.invoice_number),
        "date": bool(x.date),
        "total": x.total_value is not None,
        "items": len(x.items) > 0,
    }
