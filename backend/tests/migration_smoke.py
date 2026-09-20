"""CI-only synthetic data preservation across 0003 -> head. Never run on production."""

import asyncio
import os
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


async def main(mode):
    url = make_url(Settings().DATABASE_URL)
    if os.getenv("RUN_DB_TESTS") != "1" or url.host not in ("localhost", "127.0.0.1") or url.database != "test":
        raise RuntimeError("Migration smoke test requires an explicitly enabled local test database")
    engine = create_async_engine(url)
    ids = {
        key: uuid.uuid5(uuid.NAMESPACE_URL, "knowledgegpt-migration-smoke-" + key)
        for key in ("user", "kb", "doc", "chunk")
    }
    try:
        async with engine.begin() as db:
            version = await db.scalar(text("SELECT version_num FROM alembic_version"))
            if mode == "seed":
                assert version == "0003_token_version"
                await db.execute(text("INSERT INTO users(id,email) VALUES (:user,'migration-smoke@example.com')"), ids)
                await db.execute(
                    text(
                        "INSERT INTO knowledge_bases(id,owner_id,name) VALUES (:kb,:user,'Synthetic migration fixture')"
                    ),
                    ids,
                )
                await db.execute(
                    text(
                        "INSERT INTO documents(id,owner_id,knowledge_base_id,name,file_type,status,checksum) VALUES (:doc,:user,:kb,'synthetic.txt','txt','completed','synthetic-checksum')"
                    ),
                    ids,
                )
                await db.execute(
                    text(
                        "INSERT INTO document_chunks(id,document_id,owner_id,knowledge_base_id,chunk_index,content,embedding,embedding_model,checksum) VALUES (:chunk,:doc,:user,:kb,0,'Synthetic preserved evidence',CAST(:vector AS vector),'gemini-embedding-001','synthetic-checksum')"
                    ),
                    {**ids, "vector": "[" + ",".join(["1"] + ["0"] * 1535) + "]"},
                )
            elif mode == "verify":
                assert version == "0006_citation_order"
                row = (
                    await db.execute(
                        text(
                            "SELECT status::text, confirmed_at IS NOT NULL, retryable, error_code FROM documents WHERE id=:doc"
                        ),
                        ids,
                    )
                ).one()
                assert tuple(row) == ("completed", True, False, None)
                row = (
                    await db.execute(
                        text("SELECT content, vector_dims(embedding), structure FROM document_chunks WHERE id=:chunk"),
                        ids,
                    )
                ).one()
                assert tuple(row) == ("Synthetic preserved evidence", 1536, None)
                assert (
                    await db.scalar(text("SELECT email FROM users WHERE id=:user"), ids)
                    == "migration-smoke@example.com"
                )
                await db.execute(text("DELETE FROM users WHERE id=:user"), ids)
            else:
                raise ValueError("Use seed or verify")
        print(f"Migration smoke {mode}: passed")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
