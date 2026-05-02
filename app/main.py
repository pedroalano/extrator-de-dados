import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.routers.invoice import router as invoice_router
from app.api.routers.pdf_extract import router as pdf_extract_router
from app.config import get_settings
from app.db.mongo import get_database, mongo_lifespan
from app.utils.logging import setup_logging
from app.utils.request_context import request_id_ctx

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level, json_logs=settings.log_json)
    app.state.settings = settings
    if settings.testing:
        yield
        return
    async with mongo_lifespan(settings):
        app.state.db = get_database(settings)
        yield


_API_DESCRIPTION = (
    "Processa **XML** de NFe (produto) ou NFS-e (serviço) e **PDF** associado (DANFE ou nota de serviço), "
    "com fluxo híbrido: regras/XPath com cache em MongoDB e LLM quando necessário.\n\n"
    "Com **`ENABLE_PDF_EXTRACT_ENDPOINT=true`**, aparece também **`POST /extract-pdf`** (só PDF, testes/depuração), "
    "tag **pdf** no Swagger.\n\n"
    "Documentação interativa: [**Swagger UI** (`/docs`)](/docs) · [**ReDoc** (`/redoc`)](/redoc)."
)

_settings_at_boot = get_settings()

_OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "invoice",
        "description": (
            "Endpoints de processamento de notas fiscais. "
            "`POST /process-invoice` usa `multipart/form-data` com `xml_file` e `pdf_file`."
        ),
    },
]
if _settings_at_boot.enable_pdf_extract_endpoint:
    _OPENAPI_TAGS.append(
        {
            "name": "pdf",
            "description": (
                "Extração só-PDF para testes e depuração. "
                "Ative com `ENABLE_PDF_EXTRACT_ENDPOINT=true`."
            ),
        },
    )

app = FastAPI(
    title="Extrator de dados NFe",
    version="0.1.0",
    description=_API_DESCRIPTION,
    openapi_tags=_OPENAPI_TAGS,
    lifespan=lifespan,
    swagger_ui_parameters={"docExpansion": "list"},
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    token = request_id_ctx.set(rid)
    response = None
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = response.status_code if response is not None else 500
        logger.info(
            "http_request",
            extra={
                "http_method": request.method,
                "path": request.url.path,
                "status_code": status,
                "duration_ms": round(elapsed_ms, 3),
            },
        )
        if response is not None:
            response.headers["X-Request-ID"] = rid
        request_id_ctx.reset(token)
    return response


def _bootstrap_logging() -> None:
    s = get_settings()
    setup_logging(s.log_level, json_logs=s.log_json)


app.include_router(invoice_router)
if _settings_at_boot.enable_pdf_extract_endpoint:
    app.include_router(pdf_extract_router)

_bootstrap_logging()
