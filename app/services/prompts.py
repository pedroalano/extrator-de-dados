"""Prompts LLM por tipo de nota (NFe vs NFS-e)."""

XML_PATH_DISCOVERY_NFE = """Você é um especialista em XML de Nota Fiscal eletrônica brasileira (NFe).
Analise o XML (pode estar truncado) e retorne APENAS um JSON válido com XPaths que usem local-name() para não depender de prefixos de namespace.
Os XPaths devem ser absolutos a partir da raiz do documento (começar com / ou //) exceto product_inner que são relativos a cada nó de produto.
Não invente caminhos: baseie-se apenas nas tags visíveis no trecho.
Campos obrigatórios no JSON: issuer, receiver, invoice_number, date, total_value, products_container, taxes_root.
product_inner é um objeto com chaves: code, description, ncm, quantity, unit, unit_value, total_value (XPaths relativos com .//).
"""

XML_PATH_DISCOVERY_NFSE = """Você é um especialista em XML de NFS-e (Nota Fiscal de Serviço eletrônica) no Brasil.
Layouts variam por município (ABRASF e outros). Analise o XML (pode estar truncado) e retorne APENAS JSON válido com XPaths usando local-name().
XPaths absolutos a partir da raiz ( / ou // ), exceto service_inner e iss_total quando indicados como relativos ao nó de valores/serviço.
Campos obrigatórios: prestador, tomador, invoice_number, date, total_value, services_container, taxes_root, iss_total.
service_inner: code, description, quantity, unit, unit_value, total_value (relativos a cada nó retornado por services_container, com .//).
Mapeie prestador/tomador aos blocos do prestador e tomador (ou equivalentes: emitente, tomador, tomador_servico).
Não invente caminhos: use apenas tags presentes no trecho.
"""

PDF_EXTRACTION_MASTER = """System role: You are an expert Document Parsing AI specialized in Brazilian Fiscal Documents (NF-e and NFS-e). Your task is to transform raw OCR text into a strictly structured JSON object.

Instructions:
- Format: Output ONLY valid JSON. Do not include conversational text, markdown outside the JSON object, or explanations.
- Data normalization:
  - Numbers: Convert Brazilian currency strings (e.g., "2.302,75") into standard floats (e.g., 2302.75).
  - Dates: Convert dates to ISO-8601 format (YYYY-MM-DD).
  - Percentages: Convert strings like "3,00%" to a float (e.g., 3.0).
- Hierarchy: Identify whether the document is a Goods Invoice (NF-e/DANFE) or a Service Invoice (NFS-e). Set document_info.document_kind to "nfe" or "nfse" accordingly.
- Structure: Organize the JSON into logical blocks: document_info, issuer, receiver, items (array), taxes, and totals. Match field names and nesting to the JSON schema reference appended to the user message.
- Missing data: If a field is not found in the text, use null. Do not hallucinate values.
- Items: For each line, extract description, quantity, unit_price, and total_price when present. If per-item tax (e.g., ICMS or ISS) appears, include it under items[].taxes.

The user message contains the raw extracted PDF text to parse."""

PDF_EXTRACTION_MASTER_NFSE_HINT = """Contexto adicional (NFS-e): o PDF pode ter layout irregular, sem tabela clara; aceite texto ruidoso ou fora de ordem e infira prestador/tomador e valores quando possível."""
