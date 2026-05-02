"""Regressão: readiness, métricas Prometheus e correlação de logs."""

from __future__ import annotations

import logging


def test_ready_ok_when_testing(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_requests" in body or "prometheus" in body.lower() or "python_info" in body


def test_health_response_includes_request_id_header(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "x-request-id" in {k.lower(): v for k, v in r.headers.items()}


def test_access_log_record_has_path_and_request_id(client, caplog):
    caplog.set_level(logging.INFO, logger="app.main")

    client.get("/health")

    http_req = None
    for r in caplog.records:
        if r.name == "app.main" and r.getMessage() == "http_request":
            http_req = r
            break

    assert http_req is not None, caplog.text
    assert http_req.path == "/health"
    assert http_req.status_code == 200
    assert http_req.request_id != "-"
