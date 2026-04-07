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


app = FastAPI(
    title="Extrator de dados NFe",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


app.include_router(invoice_router)
