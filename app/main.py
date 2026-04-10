import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.routers.invoice import router as invoice_router
from app.config import get_settings
from app.db.mongo import get_database, mongo_lifespan
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
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
    "Documentação interativa: [**Swagger UI** (`/docs`)](/docs) · [**ReDoc** (`/redoc`)](/redoc)."
)

_OPENAPI_TAGS = [
    {
        "name": "invoice",
        "description": (
            "Endpoints de processamento de notas fiscais. "
            "`POST /process-invoice` usa `multipart/form-data` com `xml_file` e `pdf_file`."
        ),
    },
]

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
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


app.include_router(invoice_router)
