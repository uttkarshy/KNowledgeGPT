"""Runtime validation; schema/model changes require deliberate re-embedding."""
from sqlalchemy import text

from app.core.config import Settings


async def check_embedding_contract(connection, settings: Settings) -> None:
    dimension = await connection.scalar(text("""SELECT format_type(atttypid, atttypmod)
        FROM pg_attribute WHERE attrelid = 'document_chunks'::regclass AND attname = 'embedding'"""))
    if dimension != "vector(1536)":
        raise RuntimeError("Embedding schema mismatch; run migrations and re-embed saved chunk text")
    models = (await connection.execute(text("SELECT DISTINCT embedding_model FROM document_chunks"))).scalars().all()
    if any(model != settings.LLM_EMBEDDING_MODEL for model in models):
        raise RuntimeError("Existing vectors use another embedding model. Back up and re-embed before changing providers.")
