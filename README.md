# Extrator de dados — NFe (XML + PDF)

API **FastAPI** assíncrona que processa **XML de NFe** e **PDF (DANFE)** com fluxo híbrido: regras/XPath com cache em **MongoDB** e **LLM** só quando necessário (novo layout XML ou PDF com baixa qualidade de texto).

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
| `OPENAI_API_KEY` | Chave da API (vazia = sem LLM; XML usa mapeamento NFe padrão) |
| `OPENAI_BASE_URL` | Base URL compatível OpenAI |
| `OPENAI_MODEL` | Modelo |
| `MAX_UPLOAD_BYTES` | Tamanho máximo por arquivo |
| `PDF_CACHE_MAX_ENTRIES` | LRU em memória para resultados de PDF |
| `STORE_PROCESSED_METADATA` | Gravar metadados em `processed_invoices` |

## Endpoint

`POST /process-invoice` — `multipart/form-data`:

- `xml_file`: arquivo `.xml`
- `pdf_file`: arquivo `.pdf`

### Exemplo com curl

```bash
curl -s -X POST "http://localhost:8000/process-invoice" \
  -H "X-Request-ID: meu-id-opcional" \
  -F "xml_file=@/caminho/nota.xml;type=application/xml" \
  -F "pdf_file=@/caminho/danfe.pdf;type=application/pdf"
```

Resposta JSON inclui `issuer`, `receiver`, `total_value`, `products`, `taxes`, `date`, `invoice_number`, além de `structure_hash`, `used_llm_xml`, `used_llm_pdf` e `warnings`.

## Comportamento resumido

1. **XML:** calcula fingerprint estrutural → busca `xml_mappings` no Mongo → se não existir e houver chave LLM, envia amostra do XML ao modelo para obter XPaths; persiste o mapeamento; extrai dados com `lxml`.
2. **PDF:** extrai texto com **PyMuPDF**; avalia heurística de qualidade; se necessário (e houver chave), envia texto ao LLM.
3. **Fusão:** prioriza dados do XML; PDF preenche lacunas.

**OCR** não está incluído: PDFs somente imagem tendem a baixa qualidade de texto e o LLM receberá pouco conteúdo.

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
  models/
  db/
  utils/
```
