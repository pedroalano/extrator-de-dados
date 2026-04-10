from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from app.api.deps import PdfProcessorDep, SettingsDep
from app.api.validators import validate_pdf_bytes
from app.models.domain import HTTPErrorResponse
from app.models.pdf_extract import (
    PdfExtractResponse,
    pdf_side_data_to_response,
    simulated_xml_coverage,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])

_EXTRACT_PDF_DESCRIPTION = (
    "Extrai dados **apenas do PDF** (PyMuPDF + heurísticas; LLM opcional conforme qualidade e "
    "`simulate_xml_complete`). Útil para testes e depuração.\n\n"
    "**Requer** `ENABLE_PDF_EXTRACT_ENDPOINT=true` na API (caso contrário a rota não é registada).\n\n"
    "- **`simulate_xml_complete`**: se `true`, simula XML com todos os campos preenchidos (afeta quando o LLM "
    "do PDF é acionado); se `false`, simula cobertura XML vazia."
)

_EXTRACT_PDF_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": "Extração concluída (heurística e/ou LLM conforme parâmetros e `OPENAI_API_KEY`).",
    },
    400: {
        "model": HTTPErrorResponse,
        "description": "PDF inválido ou vazio.",
    },
    413: {
        "model": HTTPErrorResponse,
        "description": "Arquivo acima de `MAX_UPLOAD_BYTES`.",
    },
    422: {
        "model": HTTPErrorResponse,
        "description": "Arquivo não é `.pdf`.",
    },
    500: {
        "model": HTTPErrorResponse,
        "description": "Falha ao processar o PDF.",
    },
}


@router.post(
    "/extract-pdf",
    response_model=PdfExtractResponse,
    summary="Extrair dados só do PDF (testes)",
    description=_EXTRACT_PDF_DESCRIPTION,
    responses=_EXTRACT_PDF_RESPONSES,
    operation_id="extractPdf",
)
async def extract_pdf(
    settings: SettingsDep,
    pdf_processor: PdfProcessorDep,
    invoice_type: Annotated[
        Literal["nfe", "nfse"],
        Query(
            description="Tipo de nota para prompts e heurísticas (NFe vs NFS-e).",
            openapi_examples={
                "nfe": {"summary": "NFe (produto)", "value": "nfe"},
                "nfse": {"summary": "NFS-e (serviço)", "value": "nfse"},
            },
        ),
    ],
    skip_llm: Annotated[
        bool,
        Query(description="Se true, não chama o LLM no PDF mesmo quando a lógica pediria."),
    ] = False,
    simulate_xml_complete: Annotated[
        bool,
        Query(
            description="Se true, `xml_coverage` simulada com todos os campos; se false, todos vazios."
        ),
    ] = False,
    _: Annotated[
        str | None,
        Header(
            alias="X-Request-ID",
            description="ID opcional de correlação; ecoado na resposta pelo middleware global.",
        ),
    ] = None,
    pdf_file: UploadFile = File(..., description="Arquivo PDF (DANFE, NFS-e, etc.)"),
) -> PdfExtractResponse:
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="pdf_file deve ser .pdf")

    pdf_bytes = await pdf_file.read()
    max_b = settings.max_upload_bytes
    if len(pdf_bytes) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"PDF excede limite de {max_b} bytes",
        )

    validate_pdf_bytes(pdf_bytes)

    has_api_key = bool(settings.llm_api_key.strip())
    xml_coverage = simulated_xml_coverage(simulate_xml_complete)

    try:
        side = await pdf_processor.process(
            pdf_bytes,
            skip_llm=skip_llm,
            has_api_key=has_api_key,
            xml_coverage=xml_coverage,
            invoice_type=invoice_type,
        )
    except Exception as e:
        logger.exception("Erro ao processar PDF (extract-pdf)")
        raise HTTPException(status_code=500, detail="Falha ao processar PDF") from e

    return pdf_side_data_to_response(side, invoice_type=invoice_type)
