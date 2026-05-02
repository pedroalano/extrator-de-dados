import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.config import Settings

logger = logging.getLogger(__name__)


def setup_prometheus(app: "FastAPI", *, enabled: bool) -> None:
    if not enabled:
        return
    Instrumentator().instrument(app).expose(app)
    logger.info("Prometheus metrics expostos em /metrics")


def setup_opentelemetry(app: "FastAPI", settings: "Settings") -> None:
    if not settings.enable_otel:
        return

    resource = Resource.create(
        {
            "service.name": settings.app_name,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otlp_traces_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otlp_traces_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OpenTelemetry exportando traces para %s", settings.otlp_traces_endpoint)
    else:
        logger.warning(
            "ENABLE_OTEL=true mas OTEL_EXPORTER_OTLP_TRACES_ENDPOINT vazio; "
            "spans não são exportados"
        )

    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    PymongoInstrumentor().instrument()

    logger.info("OpenTelemetry instrumentação activa (FastAPI, HTTPX, PyMongo)")
