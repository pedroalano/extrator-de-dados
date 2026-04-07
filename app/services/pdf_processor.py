from __future__ import annotations

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass, field

import fitz

from app.config import Settings
from app.models.ai_schemas import PdfExtractionLLMResponse
from app.models.domain import Party, ProductLine
from app.services.ai_service import AIService, PDF_EXTRACTION_SYSTEM
from app.utils.hashing import sha256_bytes

logger = logging.getLogger(__name__)

CNPJ_RE = re.compile(
    r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b"
)
DATE_RE = re.compile(
    r"\b\d{2}/\d{2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b"
)
MONEY_RE = re.compile(r"R\$\s*[\d\.\s]+,\d{2}", re.IGNORECASE)


def _party_meaningful(p: Party | None) -> bool:
    if p is None:
        return False
    return bool(p.name or p.cnpj or p.cpf or p.address)


@dataclass
class PdfSideData:
    issuer: Party | None = None
    receiver: Party | None = None
    invoice_number: str | None = None
    date: str | None = None
    total_value: float | None = None
    products: list[ProductLine] = field(default_factory=list)
    taxes_note: str | None = None
    used_llm: bool = False
    quality_score: float = 0.0
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)


def _normalize_cnpj(s: str) -> str:
    return re.sub(r"\D", "", s)


def _heuristic_quality(text: str, pdf_size: int) -> float:
    t = text.strip()
    if not pdf_size:
        return 0.0
    printable = sum(1 for c in t if c.isprintable() or c in "\n\r\t")
    printable_ratio = printable / max(len(t), 1)
    density = min(1.0, len(t) / max(pdf_size, 1) * 80)
    score = 0.4 * printable_ratio + 0.4 * density
    if CNPJ_RE.search(t):
        score += 0.15
    if DATE_RE.search(t):
        score += 0.1
    if MONEY_RE.search(t):
        score += 0.1
    if len(t) < 200:
        score *= 0.5
    return min(1.0, score)


def _deterministic_from_text(text: str) -> PdfSideData:
    cnpjs = CNPJ_RE.findall(text)
    issuer_cnpj = receiver_cnpj = None
    if len(cnpjs) >= 1:
        issuer_cnpj = _normalize_cnpj(cnpjs[0]) if len(cnpjs[0]) == 14 else cnpjs[0]
    if len(cnpjs) >= 2:
        receiver_cnpj = _normalize_cnpj(cnpjs[1]) if len(cnpjs[1]) == 14 else cnpjs[1]

    dates = DATE_RE.findall(text)
    dt = dates[0] if dates else None

    nf_match = re.search(
        r"(?:N[ºo°]\s*(?:da\s*)?(?:NF|Nota)|Nota Fiscal).*?(\d{6,10})",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    inv_num = nf_match.group(1) if nf_match else None

    return PdfSideData(
        issuer=Party(cnpj=issuer_cnpj) if issuer_cnpj else None,
        receiver=Party(cnpj=receiver_cnpj) if receiver_cnpj else None,
        invoice_number=inv_num,
        date=dt,
        raw_text=text,
    )


def _safe_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(".", "").replace(",", ".") if "," in str(v) else str(v)
        return float(s)
    except (ValueError, TypeError):
        return None


def _llm_response_to_side(data: PdfExtractionLLMResponse) -> PdfSideData:
    products: list[ProductLine] = []
    for p in data.products:
        if not isinstance(p, dict):
            continue
        products.append(
            ProductLine(
                code=p.get("code") if isinstance(p.get("code"), str) else None,
                description=p.get("description")
                if isinstance(p.get("description"), str)
                else None,
                quantity=_safe_float(p.get("quantity")),
                unit_value=_safe_float(p.get("unit_value")),
                total_value=_safe_float(p.get("total_value")),
            )
        )
    return PdfSideData(
        issuer=Party(
            name=data.issuer_name,
            cnpj=data.issuer_cnpj,
        )
        if (data.issuer_name or data.issuer_cnpj)
        else None,
        receiver=Party(
            name=data.receiver_name,
            cnpj=data.receiver_cnpj,
        )
        if (data.receiver_name or data.receiver_cnpj)
        else None,
        invoice_number=data.invoice_number,
        date=data.date,
        total_value=data.total_value,
        products=products,
        taxes_note=data.taxes_note,
        used_llm=True,
    )


class PdfProcessor:
    def __init__(self, settings: Settings, ai: AIService) -> None:
        self._settings = settings
        self._ai = ai
        self._cache: OrderedDict[str, PdfSideData] = OrderedDict()

    def _cache_get(self, key: str) -> PdfSideData | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_set(self, key: str, value: PdfSideData) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._settings.pdf_cache_max_entries:
            self._cache.popitem(last=False)

    def extract_text(self, pdf_bytes: bytes) -> tuple[str, int]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            parts: list[str] = []
            for page in doc:
                parts.append(page.get_text() or "")
            text = "\n".join(parts)
            return text, len(pdf_bytes)
        finally:
            doc.close()

    def _xml_covers_minimum(self, xml_has: dict[str, bool]) -> bool:
        return all(xml_has.values())

    async def process(
        self,
        pdf_bytes: bytes,
        *,
        skip_llm: bool,
        has_api_key: bool,
        xml_coverage: dict[str, bool],
    ) -> PdfSideData:
        key = sha256_bytes(pdf_bytes)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        text, size = self.extract_text(pdf_bytes)
        quality = _heuristic_quality(text, size)
        det = _deterministic_from_text(text)
        det.quality_score = quality
        det.raw_text = text[:5000]

        if self._xml_covers_minimum(xml_coverage):
            need_llm = quality < 0.45
        else:
            need_llm = quality < 0.5 or len(det.products) == 0

        if need_llm and skip_llm:
            need_llm = False

        if need_llm and has_api_key:
            try:
                user = f"Texto extraído do PDF (truncado):\n{text[: self._settings.llm_max_input_chars]}"
                llm_out = await self._ai.complete_json(
                    system_prompt=PDF_EXTRACTION_SYSTEM,
                    user_prompt=user,
                    response_model=PdfExtractionLLMResponse,
                    max_tokens=4096,
                )
                merged = _merge_det_llm(det, _llm_response_to_side(llm_out))
                self._cache_set(key, merged)
                return merged
            except Exception as e:
                logger.warning("Fallback PDF sem LLM após erro: %s", e)
                det.warnings.append(f"pdf_llm_error: {e!s}")
                self._cache_set(key, det)
                return det

        self._cache_set(key, det)
        return det


def _merge_det_llm(det: PdfSideData, llm: PdfSideData) -> PdfSideData:
    def pick_str(a: str | None, b: str | None) -> str | None:
        return a or b

    def pick_party(d: Party | None, l: Party | None) -> Party | None:
        if not _party_meaningful(d) and not _party_meaningful(l):
            return None
        if not _party_meaningful(d):
            return l
        if not _party_meaningful(l):
            return d
        return Party(
            name=pick_str(d.name, l.name),
            cnpj=pick_str(d.cnpj, l.cnpj),
            cpf=pick_str(d.cpf, l.cpf),
            address=pick_str(d.address, l.address),
        )

    products = llm.products if llm.products else det.products
    return PdfSideData(
        issuer=pick_party(det.issuer, llm.issuer),
        receiver=pick_party(det.receiver, llm.receiver),
        invoice_number=pick_str(det.invoice_number, llm.invoice_number),
        date=pick_str(det.date, llm.date),
        total_value=det.total_value if det.total_value is not None else llm.total_value,
        products=products,
        taxes_note=llm.taxes_note,
        used_llm=llm.used_llm,
        quality_score=max(det.quality_score, llm.quality_score),
        raw_text=det.raw_text,
    )
