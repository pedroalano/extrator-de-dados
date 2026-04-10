from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.models.invoice_types import InvoiceType


class XmlMappingRepository:
    collection_name = "xml_mappings"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[self.collection_name]

    async def find_by_hash(
        self, structure_hash: str, invoice_type: InvoiceType
    ) -> dict[str, Any] | None:
        doc = await self._col.find_one(
            {"structure_hash": structure_hash, "invoice_type": invoice_type}
        )
        if doc is None and invoice_type == "nfe":
            doc = await self._col.find_one(
                {
                    "structure_hash": structure_hash,
                    "invoice_type": {"$exists": False},
                }
            )
        return doc

    async def upsert_mapping(
        self,
        structure_hash: str,
        invoice_type: InvoiceType,
        mapping: BaseModel,
    ) -> None:
        now = datetime.now(timezone.utc)
        doc = {
            "structure_hash": structure_hash,
            "invoice_type": invoice_type,
            "xpath_mappings": mapping.model_dump(),
            "created_at": now,
        }
        await self._col.update_one(
            {"structure_hash": structure_hash, "invoice_type": invoice_type},
            {"$set": doc},
            upsert=True,
        )


class ProcessedInvoiceRepository:
    collection_name = "processed_invoices"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[self.collection_name]

    async def insert_metadata(self, record: dict[str, Any]) -> None:
        record.setdefault("created_at", datetime.now(timezone.utc))
        await self._col.insert_one(record)
