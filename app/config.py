from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    mongodb_url: str = Field(default="mongodb://localhost:27017")
    mongodb_db: str = Field(default="nfe_processor")

    max_upload_bytes: int = Field(default=15 * 1024 * 1024, description="Limite por arquivo")

    llm_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="OPENAI_BASE_URL",
    )
    llm_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    llm_timeout_seconds: float = 120.0
    llm_max_tokens: int = 4096
    llm_max_input_chars: int = 24_000
    llm_temperature: float = 0.0

    pdf_cache_max_entries: int = 256

    store_processed_metadata: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
