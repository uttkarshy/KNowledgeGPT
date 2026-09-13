import os

# Set before any `app.*` import happens, since app.core.config.get_settings()
# is evaluated at import time in several modules (e.g. chunk.py reads
# LLM_EMBEDDING_DIMENSIONS for the pgvector column size).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("LLM_EMBEDDING_DIMENSIONS", "1536")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-ci-only")
