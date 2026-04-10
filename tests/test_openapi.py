"""Regressão mínima do schema OpenAPI exposto em `/openapi.json`."""

from __future__ import annotations

import pytest

from app.main import app


@pytest.fixture
def openapi_schema():
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        r = client.get("/openapi.json")
        assert r.status_code == 200, r.text
        return r.json()


def test_openapi_paths_and_operations(openapi_schema: dict):
    paths = openapi_schema["paths"]
    assert "/process-invoice" in paths
    assert "/health" in paths
    assert "post" in paths["/process-invoice"]
    assert "get" in paths["/health"]


def test_openapi_invoice_tag_and_process_invoice_metadata(openapi_schema: dict):
    tag_names = {t["name"] for t in openapi_schema.get("tags", [])}
    assert "invoice" in tag_names

    post = openapi_schema["paths"]["/process-invoice"]["post"]
    assert post.get("summary")
    assert post.get("description")
    assert "invoice" in post.get("tags", [])

    responses = post["responses"]
    assert "200" in responses
    for code in ("400", "413", "422", "500"):
        assert code in responses, f"missing documented response {code}"


def test_openapi_process_invoice_has_request_id_header_param(openapi_schema: dict):
    params = openapi_schema["paths"]["/process-invoice"]["post"].get("parameters") or []
    header_params = [p for p in params if p.get("in") == "header"]
    names = {p.get("name") for p in header_params}
    assert "X-Request-ID" in names


def test_openapi_invoice_process_response_has_example(openapi_schema: dict):
    ref = openapi_schema["paths"]["/process-invoice"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    # response_model: $ref ou allOf com exemplo no componente
    assert "$ref" in ref
    name = ref["$ref"].split("/")[-1]
    schema = openapi_schema["components"]["schemas"][name]
    assert "example" in schema or "examples" in str(schema)


def test_openapi_health_summary(openapi_schema: dict):
    get_op = openapi_schema["paths"]["/health"]["get"]
    assert get_op.get("summary")
    assert get_op.get("description")


def test_openapi_pdf_extract_router_schema():
    """Schema do router `pdf` sem depender de ENABLE_PDF_EXTRACT_ENDPOINT na app principal."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers.pdf_extract import router as pdf_router

    mini = FastAPI()
    mini.include_router(pdf_router)
    with TestClient(mini) as client:
        spec = client.get("/openapi.json").json()

    post = spec["paths"]["/extract-pdf"]["post"]
    assert post.get("operationId") == "extractPdf"
    assert "200" in post["responses"]
    assert post["responses"]["200"].get("description")

    params = post.get("parameters") or []
    assert any(p.get("name") == "X-Request-ID" and p.get("in") == "header" for p in params)

    ref = post["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in ref
    name = ref["$ref"].split("/")[-1]
    comp = spec["components"]["schemas"][name]
    assert "example" in comp or "examples" in str(comp)
