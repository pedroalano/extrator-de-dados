from typing import Annotated

from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.db.repositories import ProcessedInvoiceRepository, XmlMappingRepository
from app.services.ai_service import AIService
from app.services.gemini_ai_service import GeminiAIService
from app.services.openai_ai_service import OpenAICompatibleAIService
from app.services.pdf_processor import PdfProcessor
from app.services.xml_processor import XmlProcessor


def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


def get_settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]


def get_ai_service(settings: SettingsDep) -> AIService:
    if settings.llm_provider == "gemini":
        return GeminiAIService(settings)
    return OpenAICompatibleAIService(settings)


AiServiceDep = Annotated[AIService, Depends(get_ai_service)]


def get_xml_repo(db: DbDep) -> XmlMappingRepository:
    return XmlMappingRepository(db)


XmlRepoDep = Annotated[XmlMappingRepository, Depends(get_xml_repo)]


def get_processed_repo(db: DbDep) -> ProcessedInvoiceRepository:
    return ProcessedInvoiceRepository(db)


ProcessedRepoDep = Annotated[
    ProcessedInvoiceRepository, Depends(get_processed_repo)
]


def get_xml_processor(
    repo: XmlRepoDep,
    ai: AiServiceDep,
) -> XmlProcessor:
    return XmlProcessor(repo, ai)


XmlProcessorDep = Annotated[XmlProcessor, Depends(get_xml_processor)]


def get_pdf_processor(
    settings: SettingsDep,
    ai: AiServiceDep,
) -> PdfProcessor:
    return PdfProcessor(settings, ai)


PdfProcessorDep = Annotated[PdfProcessor, Depends(get_pdf_processor)]


__all__ = [
    "AiServiceDep",
    "DbDep",
    "PdfProcessorDep",
    "ProcessedRepoDep",
    "SettingsDep",
    "XmlProcessorDep",
    "XmlRepoDep",
    "get_ai_service",
    "get_db",
    "get_settings_dep",
]
