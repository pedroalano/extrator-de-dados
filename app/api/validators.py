"""Validações partilhadas entre rotas (bytes de upload)."""

from fastapi import HTTPException


def validate_pdf_bytes(data: bytes) -> None:
    if not data or len(data) < 5:
        raise HTTPException(status_code=400, detail="PDF vazio ou muito curto")
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400, detail="Arquivo PDF inválido (cabeçalho %PDF ausente)"
        )
