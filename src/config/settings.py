from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM Gateway (OpenRouter — OpenAI-compatible API)
    openrouter_api_key: SecretStr = SecretStr("")

    # Cohere
    cohere_api_key: SecretStr = SecretStr("")

    # Lakera Guard
    lakera_api_key: SecretStr = SecretStr("")

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: SecretStr = SecretStr("")

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "http://localhost:3100"

    # Application
    pipeline_env: str = "development"
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"
