"""
Application configuration.

Design principle: NOTHING model-specific is hardcoded anywhere in the codebase.
All model names, providers, and tunables are read from environment variables
(backed by AWS Secrets Manager / SSM in production via the same env interface).

To switch LLM providers or models, an operator only ever needs to change:
  - LLM_PROVIDER
  - LLM_CHAT_MODEL
  - LLM_EMBEDDING_MODEL
No application code changes are required.
"""

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderName(str, Enum):
    """Supported LLM provider backends.

    New providers are added here and in services/llm/factory.py ONLY.
    No other file in the codebase should ever branch on provider name.
    """

    OPENAI = "openai"
    LOCAL_VLLM = "local_vllm"          # future
    LOCAL_OLLAMA = "local_ollama"      # future
    NVIDIA_NIM = "nvidia_nim"          # future
    LLAMA_CPP = "llama_cpp"            # future
    HUGGINGFACE = "huggingface"        # future


class Settings(BaseSettings):
    """Central application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------
    # Core app
    # ---------------------------------------------------------------
    APP_NAME: str = "KnowledgeGPT"
    ENVIRONMENT: str = Field(default="development")  # development|staging|production
    DEBUG: bool = False

    # ---------------------------------------------------------------
    # Auth / JWT
    # ---------------------------------------------------------------
    JWT_SECRET_KEY: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-use-a-256-bit-random-secret",
        description="Loaded from AWS Secrets Manager in production. Rotate via "
        "JWT_SECRET_KEY_PREVIOUS to allow zero-downtime rotation (both are "
        "accepted for verification during rollover; only the current one signs).",
    )
    JWT_SECRET_KEY_PREVIOUS: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # ---------------------------------------------------------------
    # Google OAuth
    # ---------------------------------------------------------------
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # ---------------------------------------------------------------
    # Frontend / email
    # ---------------------------------------------------------------
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    EMAIL_FROM: str = "noreply@knowledgegpt.example.com"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True

    # ---------------------------------------------------------------
    # Rate limiting (Redis-backed, used by app.core.rate_limit)
    # ---------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_REGISTER_PER_MINUTE: int = 3
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60

    # ---------------------------------------------------------------
    # AWS / S3 (temporary upload storage — originals deleted post-embedding)
    # ---------------------------------------------------------------
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "knowledgegpt-uploads"
    S3_UPLOAD_PREFIX: str = "uploads"
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 900  # 15 minutes to complete the PUT
    # Populated automatically by the AWS SDK's default credential chain
    # (IAM role in production; env vars / ~/.aws/credentials in dev).
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_ENDPOINT_URL: Optional[str] = None  # for LocalStack / MinIO in dev

    # ---------------------------------------------------------------
    # Upload validation
    # ---------------------------------------------------------------
    MAX_UPLOAD_SIZE_BYTES: int = 200 * 1024 * 1024  # 200 MB per file
    ALLOWED_FILE_EXTENSIONS: list[str] = Field(
        default_factory=lambda: [
            "pdf", "docx", "doc", "txt", "csv", "xlsx", "xls", "pptx",
            "md", "markdown", "html", "htm", "xml", "json", "rtf",
            "png", "jpg", "jpeg", "tiff", "bmp", "zip",
        ]
    )

    # ---------------------------------------------------------------
    # Virus scanning (ClamAV) — placeholder wiring, see services/upload/virus_scan.py
    # ---------------------------------------------------------------
    VIRUS_SCAN_ENABLED: bool = True  # ClamAV daemon expected to be deployed alongside
    CLAMAV_HOST: str = "localhost"
    CLAMAV_PORT: int = 3310

    # ---------------------------------------------------------------
    # Celery / background workers
    # ---------------------------------------------------------------
    CELERY_BROKER_URL: Optional[str] = None    # falls back to REDIS_URL if unset
    CELERY_RESULT_BACKEND: Optional[str] = None  # falls back to REDIS_URL if unset
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_RETRY_BACKOFF_SECONDS: int = 30

    # ---------------------------------------------------------------
    # CORS
    # ---------------------------------------------------------------
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Frontend origins allowed to call this API with credentials.",
    )

    # ---------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://knowledgegpt:knowledgegpt@localhost:5432/knowledgegpt",
        description="Async SQLAlchemy connection string. In production this "
        "is injected via AWS Secrets Manager, same env-var interface.",
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # ---------------------------------------------------------------
    # LLM provider selection — the ONLY place provider choice is made
    # ---------------------------------------------------------------
    LLM_PROVIDER: LLMProviderName = LLMProviderName.OPENAI

    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None  # allows Azure/OpenAI-compatible proxies

    # Model names are pure config — never referenced as literals elsewhere.
    LLM_CHAT_MODEL: str = Field(
        default="gpt-4.1",
        description="Chat/completion model name used via the Responses API.",
    )
    LLM_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-large",
        description="Embedding model name.",
    )
    LLM_EMBEDDING_DIMENSIONS: int = Field(
        default=1536,
        description="Must match the pgvector column dimension for the chosen embedding model.",
    )

    # Generation tunables — also fully configurable, never hardcoded in providers
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_OUTPUT_TOKENS: int = 2048
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_RETRIES: int = 3

    # RAG behavior
    RAG_TOP_K: int = 8
    RAG_MIN_SIMILARITY: float = 0.72
    RAG_NO_ANSWER_MESSAGE: str = (
        "I couldn't find that information in your uploaded documents."
    )

    # Future local-inference endpoints (used once those providers are implemented)
    LOCAL_LLM_BASE_URL: Optional[str] = None
    LOCAL_LLM_API_KEY: Optional[str] = None

    @field_validator("LLM_PROVIDER", mode="before")
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        return v.lower() if isinstance(v, str) else v


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import this everywhere instead of instantiating Settings()."""
    return Settings()
