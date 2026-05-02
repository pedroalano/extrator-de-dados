from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["openai", "gemini"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "extrator-de-dados"
    debug: bool = False
    testing: bool = Field(default=False, alias="TESTING")
    log_level: str = "INFO"
    log_json: bool = Field(default=True, alias="LOG_JSON")

    mongodb_url: str = Field(default="mongodb://localhost:27017")
    mongodb_db: str = Field(default="nfe_processor")

    max_upload_bytes: int = Field(default=15 * 1024 * 1024, description="Limite por arquivo")

    llm_provider: LlmProvider = Field(
        default="openai",
        alias="LLM_PROVIDER",
        description="openai (API compatível OpenAI) ou gemini (Google AI Studio)",
    )

    llm_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="OPENAI_BASE_URL",
    )
    llm_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com",
        alias="GEMINI_BASE_URL",
    )
    llm_timeout_seconds: float = 120.0
    llm_max_tokens: int = 4096
    llm_max_input_chars: int = 24_000
    llm_temperature: float = 0.0

    pdf_cache_max_entries: int = 256

    pdf_raw_text_max_chars: int = Field(
        default=100_000,
        ge=1,
        alias="PDF_RAW_TEXT_MAX_CHARS",
        description=(
            "Máximo de caracteres do texto extraído do PDF incluídos em `raw_text` "
            "(resposta API / fusão)."
        ),
    )

    store_processed_metadata: bool = True

    enable_pdf_extract_endpoint: bool = Field(
        default=False,
        alias="ENABLE_PDF_EXTRACT_ENDPOINT",
        description="Expõe POST /extract-pdf (testes/depuração de extração só-PDF)",
    )

    def has_llm_credentials(self) -> bool:
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key.strip())
        return bool(self.llm_api_key.strip())

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_llm_provider(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
