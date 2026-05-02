from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from lxml import etree

from app.api.deps import (
    PdfProcessorDep,
    ProcessedRepoDep,
    SettingsDep,
    XmlProcessorDep,
)
from app.api.validators import validate_pdf_bytes
from app.models.domain import HTTPErrorResponse, InvoiceProcessResponse
from app.services.invoice_merge import merge_invoice, xml_field_coverage
from app.services.invoice_type_detection import detect_invoice_type
from app.utils.hashing import sha256_bytes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invoice"])

_PROCESS_INVOICE_DESCRIPTION = (
    "Envie **dois arquivos** em `multipart/form-data`: `xml_file` (`.xml`) e `pdf_file` (`.pdf`). "
    "O tipo da nota (NFe ou NFS-e) é detectado pelo XML.\n\n"
    "Campo opcional **`pdf_llm_input`**: `text` (texto extraído do PDF com pdfplumber e fallback PyMuPDF, predefinido) ou `pdf` (envio do PDF ao LLM ainda "
    "não implementado; usa texto e pode acrescentar aviso em `warnings`).\n\n"
    "Cada arquivo deve respeitar o limite configurado em **`MAX_UPLOAD_BYTES`**.\n\n"
    "Com **`LLM_PROVIDER=openai`** e **`OPENAI_API_KEY`** vazia (ou **`LLM_PROVIDER=gemini`** sem **`GEMINI_API_KEY`**), "
    "o LLM não é usado; o XML segue mapeamento em cache ou padrão por tipo, e o PDF usa heurísticas determinísticas quando possível."
)

_PROCESS_INVOICE_RESPONSES: dict[int, dict[str, object]] = {
    400: {
        "model": HTTPErrorResponse,
        "description": "XML ou PDF inválido (vazio, malformado ou sem cabeçalho PDF esperado).",
    },
    413: {
        "model": HTTPErrorResponse,
        "description": "Tamanho de `xml_file` ou `pdf_file` acima de `MAX_UPLOAD_BYTES`.",
    },
    422: {
        "model": HTTPErrorResponse,
        "description": "Extensão ou nome de arquivo incorreto (ex.: não é `.xml`/`.pdf`) ou corpo da requisição inválido.",
    },
    500: {
        "model": HTTPErrorResponse,
        "description": "Falha interna ao processar XML ou PDF.",
    },
}


def _validate_xml_bytes(data: bytes) -> None:
    if not data or len(data) < 10:
        raise HTTPException(status_code=400, detail="XML vazio ou muito curto")
    try:
        etree.fromstring(data)
    except etree.XMLSyntaxError as e:
        raise HTTPException(
            status_code=400, detail=f"XML inválido: {e!s}"
        ) from e


@router.post(
    "/process-invoice",
    response_model=InvoiceProcessResponse,
    summary="Processar NFe ou NFS-e (XML + PDF)",
    description=_PROCESS_INVOICE_DESCRIPTION,
    responses=_PROCESS_INVOICE_RESPONSES,
)
async def process_invoice(
    request: Request,
    settings: SettingsDep,
    xml_processor: XmlProcessorDep,
    pdf_processor: PdfProcessorDep,
    processed_repo: ProcessedRepoDep,
    _: Annotated[
        str | None,
        Header(
            alias="X-Request-ID",
            description="ID opcional de correlação; o mesmo valor é devolvido no header da resposta.",
        ),
    ] = None,
    xml_file: UploadFile = File(
        ..., description="Arquivo XML (NFe de produto ou NFS-e de serviço)"
    ),
    pdf_file: UploadFile = File(
        ..., description="PDF da nota (DANFE, NFS-e ou equivalente)"
    ),
    pdf_llm_input: Annotated[
        Literal["text", "pdf"],
        Form(
            description=(
                "Entrada do LLM sobre o PDF: `text` = texto extraído (pdfplumber + fallback PyMuPDF); `pdf` = reservado (fallback para texto + aviso)."
            ),
        ),
    ] = "text",
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
    validate_pdf_bytes(pdf_bytes)

    has_api_key = settings.has_llm_credentials()

    detected = detect_invoice_type(xml_bytes)
    invoice_type = detected.invoice_type

    try:
        xml_result = await xml_processor.process(
            xml_bytes,
            has_api_key=has_api_key,
            invoice_type=invoice_type,
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
            invoice_type=invoice_type,
            llm_input_mode=pdf_llm_input,
        )
    except Exception as e:
        logger.exception("Erro ao processar PDF")
        raise HTTPException(
            status_code=500, detail="Falha ao processar PDF"
        ) from e

    out = merge_invoice(
        xml_result, pdf_side, invoice_type=invoice_type
    )

    if settings.store_processed_metadata:
        try:
            await processed_repo.insert_metadata(
                {
                    "request_id": request_id,
                    "xml_file_hash": sha256_bytes(xml_bytes),
                    "pdf_file_hash": sha256_bytes(pdf_bytes),
                    "structure_hash": xml_result.structure_hash,
                    "invoice_type": invoice_type,
                    "used_llm_xml": out.used_llm_xml,
                    "used_llm_pdf": out.used_llm_pdf,
                    "status": "ok",
                    "created_at": datetime.now(timezone.utc),
                }
            )
        except Exception as e:
            logger.warning("Não foi possível registrar processed_invoices: %s", e)

    return out


@router.get(
    "/health",
    summary="Health check",
    description="Retorna `{\"status\": \"ok\"}` quando a API está respondendo. Use em balanceadores de carga ou smoke tests.",
)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness check",
    description=(
        "Verifica se a API pode receber tráfego (MongoDB acessível). "
        "Em `TESTING=true` (pytest) devolve 200 sem ping à BD. "
        "Resposta `503` se o Mongo não responder."
    ),
    responses={503: {"description": "MongoDB indisponível"}},
)
async def ready(settings: SettingsDep) -> dict[str, str]:
    if settings.testing:
        return {"status": "ready"}
    from app.db.mongo import get_client

    try:
        await get_client().admin.command("ping")
    except Exception as e:
        logger.warning("Readiness: MongoDB inacessível: %s", e)
        raise HTTPException(
            status_code=503,
            detail="database_unavailable",
        ) from e
    return {"status": "ready"}
