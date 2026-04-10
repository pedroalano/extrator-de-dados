import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("MongoDB client not initialized")
    return _client


def get_database(settings: Settings) -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_db]


@asynccontextmanager
async def mongo_lifespan(settings: Settings) -> AsyncIterator[None]:
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_url)
    try:
        await _client.admin.command("ping")
        db = _client[settings.mongodb_db]
        # Índice legado (só structure_hash): remover ao subir versão com invoice_type
        for legacy_name in ("structure_hash_1", "structure_hash"):
            try:
                await db.xml_mappings.drop_index(legacy_name)
            except Exception:
                pass
        await db.xml_mappings.create_index(
            [("structure_hash", 1), ("invoice_type", 1)],
            unique=True,
            name="structure_hash_invoice_type_1",
        )
        await db.processed_invoices.create_index("created_at")
        logger.info("MongoDB conectado e índices garantidos")
        yield
    finally:
        if _client is not None:
            _client.close()
            _client = None
            logger.info("MongoDB desconectado")
