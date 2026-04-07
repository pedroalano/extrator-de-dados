"""Reduz XML para envio ao LLM (custo/latência)."""

import re


def reduce_xml_for_llm(xml_bytes: bytes, max_chars: int = 18_000) -> str:
    try:
        text = xml_bytes.decode("utf-8", errors="replace")
    except Exception:
        text = xml_bytes.decode("latin-1", errors="replace")

    det_count = len(re.findall(r"<det\b", text, re.IGNORECASE))
    header = f"<!-- det_count_hint: {det_count} -->\n"

    if len(text) <= max_chars:
        return header + text

    half = max_chars // 2 - len(header) // 2
    start = text[:half]
    end = text[-half:]
    return (
        header
        + start
        + "\n<!-- ... truncated ... -->\n"
        + end
    )
