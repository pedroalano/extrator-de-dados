# Observabilidade — runbook

Guia de uso dos canais de observabilidade da API (logs, métricas Prometheus, traces OpenTelemetry) e boas práticas por ambiente.

## Visão geral: três canais

| Canal | Função | Implementação |
|-------|--------|----------------|
| **Logs** | Eventos por linha; correlacionar pedidos | JSON ou texto, `request_id`, evento `http_request` com `duration_ms` — ver [`app/utils/logging.py`](../app/utils/logging.py), middleware em [`app/main.py`](../app/main.py) |
| **Métricas** | Agregados no tempo (taxa, latência, erros) | [`prometheus-fastapi-instrumentator`](https://github.com/trallnag/prometheus-fastapi-instrumentator) → `GET /metrics` — [`app/observability.py`](../app/observability.py) |
| **Traces** | Cadeia de operações de um pedido | OpenTelemetry: FastAPI, HTTPX, PyMongo — [`app/observability.py`](../app/observability.py) |

Objectivos: **correlacionar** (mesmo `request_id` em logs e cabeçalho de resposta; traces com `service.name` consistente); **separar** liveness/readiness da exposição de métricas; **activar** export OTLP só quando existir um destino configurado.

---

## Logs

**Variáveis:** `LOG_LEVEL`, `LOG_JSON` ([`app/config.py`](../app/config.py)).

- **`LOG_JSON=true`** (predefinido): recomendado em produção — uma linha JSON por evento, compatível com agregadores (Loki, Datadog, Cloud Logging, etc.). O formatter acrescenta `timestamp` e `level`; o `RequestIdFilter` injeta **`request_id`** no contexto do pedido.
- **`LOG_JSON=false`**: útil localmente para leitura humana; o formato textual inclui `request_id`.

**Correlação:** Envie o cabeçalho **`X-Request-ID`** a partir do cliente (gateway, curl, serviço a montante) ou deixe o servidor gerar um UUID. O middleware devolve o mesmo valor em **`X-Request-ID`** na resposta e propaga-o ao logging via [`request_context`](../app/utils/request_context.py).

**Evento `http_request`:** Por cada pedido HTTP é registado um log com mensagem `http_request` e `extra`: `http_method`, `path`, `status_code`, `duration_ms`. Permite filtrar por rota, taxa de erros ou latência em ferramentas de log.

**Boas práticas:** Manter `LOG_LEVEL=INFO` em produção; usar `DEBUG` só de forma temporária e com consciência do volume e de dados sensíveis que bibliotecas possam registar.

---

## Métricas Prometheus (`ENABLE_METRICS`)

Com `ENABLE_METRICS=true`, o instrumentador regista métricas HTTP e expõe **`GET /metrics`** no mesmo processo FastAPI.

**Boas práticas:**

1. **Scrape** pelo Prometheus (ou agente compatível) em intervalo estável (ex.: 15–60 s), não depender de consultas manuais em produção.
2. **Não expor `/metrics` à Internet aberta** sem controlo — rede interna do cluster, políticas de rede ou autenticação no scrape, conforme a tua plataforma.
3. **`ENABLE_METRICS=false`** onde não houver collector (ex.: alguns testes) para reduzir superfície e ruído.

---

## Health vs readiness

Definições em [`app/api/routers/invoice.py`](../app/api/routers/invoice.py):

| Rota | Papel | Comportamento |
|------|--------|----------------|
| **`GET /health`** | Liveness | `{"status":"ok"}` — processo responde. Para probes que reiniciam o pod se a app estiver bloqueada. |
| **`GET /ready`** | Readiness | `ping` ao MongoDB; **503** se a BD estiver inacessível. Com `TESTING=true` (pytest), **200** sem consultar a BD. |

**Kubernetes:** `livenessProbe` → `/health`; `readinessProbe` → `/ready`, para retirar tráfego quando a BD falhar sem reiniciar à toa.

---

## OpenTelemetry (`ENABLE_OTEL`)

**Variáveis:** `ENABLE_OTEL`, `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_SERVICE_NAME` (mapeado para `service.name` no resource OTEL).

**Comportamento ([`app/observability.py`](../app/observability.py)):**

- `ENABLE_OTEL=false`: instrumentação OTEL não é configurada.
- `ENABLE_OTEL=true`: `TracerProvider` com `service.name`; export por OTLP **HTTP** apenas se **`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`** estiver definido (URL completa, ex. `http://collector:4318/v1/traces`). Se estiver vazio, regista-se um **warning** e **nenhum span é exportado**, embora a instrumentação (FastAPI, HTTPX, PyMongo) fique registada.

**Instrumentações automáticas:** pedidos FastAPI; chamadas HTTPX saíntes (ex.: provedores LLM); operações PyMongo.

**Boas práticas:**

1. Definir **`OTEL_SERVICE_NAME`** por serviço/ambiente para distinguir no backend de traces.
2. Apontar o endpoint OTLP para um collector que aceite OTLP HTTP na porta correcta (ex.: 4318 em stacks Grafana/Tempo).
3. Evitar `ENABLE_OTEL=true` em produção **sem** endpoint configurado, excepto para debug controlado — preferir endpoint sempre que os traces estiverem ligados.

---

## Arranque da aplicação

`_configure_observability()` em [`app/main.py`](../app/main.py) aplica logging, Prometheus e OTEL após o registo dos routers. Os valores vêm das variáveis de ambiente no arranque.

---

## Erros frequentes

| Situação | Problema |
|----------|-----------|
| `ENABLE_OTEL=true` sem URL OTLP | Spans não são exportados; apenas aviso nos logs. |
| `/metrics` público sem restrição | Superfície extra e possível exposição de métricas internas. |
| Usar `/health` como readiness com dependência de BD | Tráfego pode ir para instâncias que não conseguem persistir dados. |
| Clientes internos sem `X-Request-ID` | Perde-se correlação gateway → API → logs. |

---

## Resumo por ambiente

| Ambiente | Sugestão |
|----------|-----------|
| **Local** | `LOG_JSON=false` opcional; `ENABLE_METRICS=true` e `curl http://localhost:8000/metrics`; OTEL só com collector local (Docker) e `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` definido. |
| **Produção** | `LOG_JSON=true`, `LOG_LEVEL=INFO`, probes `/health` + `/ready`, scrape interno de `/metrics`, `ENABLE_OTEL=true` com endpoint OTLP válido e `OTEL_SERVICE_NAME` estável. |

Variáveis resumidas também em [README.md](../README.md) e [`.env.example`](../.env.example).
