# Extrator de dados — NFe e NFS-e (XML + PDF)

API **FastAPI** assíncrona que processa **XML de NFe (produto)** ou **NFS-e (serviço)** e **PDF** (DANFE ou nota de serviço) com fluxo híbrido: regras/XPath com cache em **MongoDB** e **LLM** só quando necessário (novo layout XML ou PDF com baixa qualidade de texto).

## Requisitos

- Python 3.11+
- MongoDB (ou apenas Docker Compose)
- Chave **OpenAI** (ou endpoint compatível) para descoberta de XPaths e fallback no PDF

## Execução local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edite .env: OPENAI_API_KEY, MONGODB_URL
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ou:

```bash
python main.py
```

## Docker Compose

```bash
OPENAI_API_KEY=sua-chave docker compose up --build
```

Ou use um arquivo `.env` na raiz (não versionado) com `OPENAI_API_KEY=...` e execute `docker compose up --build` (Compose lê variáveis do host para interpolação em `docker-compose.yml`).

- API: `http://localhost:8000`
- Documentação: `http://localhost:8000/docs`
- Health: `GET /health`

## Variáveis de ambiente

Ver [`.env.example`](.env.example). Principais:

| Variável | Descrição |
|----------|-----------|
| `MONGODB_URL` | URI do MongoDB |
| `MONGODB_DB` | Nome do banco |
| `OPENAI_API_KEY` | Chave da API (vazia = sem LLM; XML usa mapeamento padrão por tipo) |
| `OPENAI_BASE_URL` | Base URL compatível OpenAI |
| `OPENAI_MODEL` | Modelo |
| `MAX_UPLOAD_BYTES` | Tamanho máximo por arquivo |
| `PDF_CACHE_MAX_ENTRIES` | LRU em memória para resultados de PDF (por tipo + hash do arquivo) |
| `STORE_PROCESSED_METADATA` | Gravar metadados em `processed_invoices` |

## Endpoint

`POST /process-invoice` — `multipart/form-data`:

- `xml_file`: arquivo `.xml` (NFe ou NFS-e)
- `pdf_file`: arquivo `.pdf`

### Exemplo com curl

```bash
curl -s -X POST "http://localhost:8000/process-invoice" \
  -H "X-Request-ID: meu-id-opcional" \
  -F "xml_file=@/caminho/nota.xml;type=application/xml" \
  -F "pdf_file=@/caminho/danfe.pdf;type=application/pdf"
```

### Resposta JSON (schema unificado)

| Campo | Descrição |
|-------|-----------|
| `invoice_type` | `"nfe"` ou `"nfse"` (detecção automática pelo XML) |
| `issuer` / `receiver` | Emitente/prestador e destinatário/tomador |
| `items` | Lista de linhas: produtos (NFe) ou serviços (NFS-e) |
| `total_value` | Valor total |
| `taxes` | `icms`, `ipi`, `iss`, `pis`, `cofins`, etc. (o que existir no documento) |
| `date` | Data de emissão (ou competência, conforme XML) |
| `invoice_number` | Número da nota |
| `structure_hash` | Fingerprint estrutural do XML (inclui o tipo) |
| `used_llm_xml` / `used_llm_pdf` | Se o LLM foi usado em cada etapa |
| `warnings` | Avisos (ex.: falha parcial no PDF) |
| `extraction_sources` | Origem do mapeamento XML (`cached` / `llm` / `default`) e do PDF (`deterministic` / `llm`) |

**Breaking change:** o campo `products` foi substituído por **`items`** na resposta.

Exemplos mínimos de XML estão em [`tests/fixtures/minimal_nfe.xml`](tests/fixtures/minimal_nfe.xml) e [`tests/fixtures/minimal_nfse.xml`](tests/fixtures/minimal_nfse.xml).

## Comportamento resumido

1. **Detecção:** o XML é classificado como NFe ou NFS-e (tags raiz, namespaces, presença de prestador/tomador/serviço/ISS, etc.).
2. **XML:** calcula fingerprint estrutural **por tipo** → busca `xml_mappings` no Mongo (`structure_hash` + `invoice_type`) → se não existir e houver chave LLM, envia amostra do XML ao modelo com prompt específico (NFe ou NFS-e); persiste o mapeamento; extrai dados com `lxml`.
3. **PDF:** extrai texto com **PyMuPDF**; heurística de qualidade (com reforço para NFS-e: ISS, serviço, etc.); se necessário (e houver chave), envia texto ao LLM com prompt NFe ou NFS-e.
4. **Fusão:** prioriza dados do XML; PDF preenche lacunas (incluindo `iss` no PDF quando o XML não trouxer).

Documentos antigos em `xml_mappings` **sem** `invoice_type` são tratados como **NFe** na leitura.

**OCR** não está incluído: PDFs somente imagem tendem a baixa qualidade de texto e o LLM receberá pouco conteúdo. (Extensão futura: **pdfplumber** para tabelas em layouts muito tabulares.)

## Testes

```bash
TESTING=1 STORE_PROCESSED_METADATA=false pytest -q
```

`TESTING=true` evita conectar ao Mongo no lifespan dos testes que sobrescrevem dependências.

## Estrutura

```
app/
  main.py
  api/deps.py
  api/routers/invoice.py
  services/
    invoice_type_detection.py
    nfe_xml_service.py
    nfse_xml_service.py
    xml_processor.py
    invoice_processors.py
    prompts.py
  models/
  db/
  utils/
```
