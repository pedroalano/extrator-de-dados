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

PDF_EXTRACTION_NFE = """Você extrai dados estruturados de texto de DANFE/NFe em português.
Retorne APENAS JSON válido com chaves: issuer_name, issuer_cnpj, receiver_name, receiver_cnpj, invoice_number, date, total_value (número),
items (lista de objetos com code, description, quantity, unit_value, total_value quando existir), taxes_note (string ou null), iss (null para NFe de produto).
Use null para campos ausentes. Não invente valores."""

PDF_EXTRACTION_NFSE = """Você extrai dados de notas fiscais de SERVIÇO (NFS-e) em português. O layout do PDF é irregular (pode não haver tabela).
Retorne APENAS JSON válido com chaves: issuer_name, issuer_cnpj (prestador), receiver_name, receiver_cnpj (tomador),
invoice_number, date, total_value (número), items (lista: descrição do serviço, valores parciais se houver),
iss (valor numérico do ISS se constar), taxes_note (texto livre sobre tributos ou null).
Aceite texto ruidoso ou fora de ordem. Use null para campos ausentes. Não invente valores."""
