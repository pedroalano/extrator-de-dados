from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from lxml import etree

from app.api.deps import (
    PdfProcessorDep,
    ProcessedRepoDep,
    SettingsDep,
    XmlProcessorDep,
)
from app.models.domain import InvoiceProcessResponse
from app.services.invoice_merge import merge_invoice, xml_field_coverage
from app.utils.hashing import sha256_bytes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invoice"])


def _validate_xml_bytes(data: bytes) -> None:
    if not data or len(data) < 10:
        raise HTTPException(status_code=400, detail="XML vazio ou muito curto")
    try:
        etree.fromstring(data)
    except etree.XMLSyntaxError as e:
        raise HTTPException(
            status_code=400, detail=f"XML inválido: {e!s}"
        ) from e


def _validate_pdf_bytes(data: bytes) -> None:
    if not data or len(data) < 5:
        raise HTTPException(status_code=400, detail="PDF vazio ou muito curto")
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400, detail="Arquivo PDF inválido (cabeçalho %PDF ausente)"
        )


@router.post("/process-invoice", response_model=InvoiceProcessResponse)
async def process_invoice(
    request: Request,
    settings: SettingsDep,
    xml_processor: XmlProcessorDep,
    pdf_processor: PdfProcessorDep,
    processed_repo: ProcessedRepoDep,
    xml_file: UploadFile = File(..., description="Arquivo XML da NFe"),
    pdf_file: UploadFile = File(..., description="PDF da nota (DANFE)"),
) -> InvoiceProcessResponse:
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    if not xml_file.filename or not xml_file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=422, detail="xml_file deve ser .xml")
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="pdf_file deve ser .pdf")

    xml_bytes = await xml_file.read()
    pdf_bytes = await pdf_file.read()

    max_b = settings.max_upload_bytes
    if len(xml_bytes) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"XML excede limite de {max_b} bytes",
        )
    if len(pdf_bytes) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"PDF excede limite de {max_b} bytes",
        )

    _validate_xml_bytes(xml_bytes)
    _validate_pdf_bytes(pdf_bytes)

    has_api_key = bool(settings.llm_api_key.strip())

    try:
        xml_result = await xml_processor.process(
            xml_bytes, has_api_key=has_api_key
        )
    except etree.XMLSyntaxError as e:
        raise HTTPException(status_code=400, detail=f"XML inválido: {e!s}") from e
    except Exception as e:
        logger.exception("Erro ao processar XML")
        raise HTTPException(
            status_code=500, detail="Falha ao processar XML"
        ) from e

    coverage = xml_field_coverage(xml_result)

    try:
        pdf_side = await pdf_processor.process(
            pdf_bytes,
            skip_llm=False,
            has_api_key=has_api_key,
            xml_coverage=coverage,
        )
    except Exception as e:
        logger.exception("Erro ao processar PDF")
        raise HTTPException(
            status_code=500, detail="Falha ao processar PDF"
        ) from e

    out = merge_invoice(xml_result, pdf_side)

    if settings.store_processed_metadata:
        try:
            await processed_repo.insert_metadata(
                {
                    "request_id": request_id,
                    "xml_file_hash": sha256_bytes(xml_bytes),
                    "pdf_file_hash": sha256_bytes(pdf_bytes),
                    "structure_hash": xml_result.structure_hash,
                    "used_llm_xml": out.used_llm_xml,
                    "used_llm_pdf": out.used_llm_pdf,
                    "status": "ok",
                    "created_at": datetime.now(timezone.utc),
                }
            )
        except Exception as e:
            logger.warning("Não foi possível registrar processed_invoices: %s", e)

    return out


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
