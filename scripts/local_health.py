"""Operator-only in-container checks; no public health endpoint permissions changed."""
import asyncio
import sys

sys.path.insert(0, '/app')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from redis.asyncio import Redis
from app.core.config import get_settings
from app.core.aws import get_s3_client
from app.db.contract import check_embedding_contract
from app.services.llm.factory import get_llm_provider


async def check():
    settings = get_settings()
    if settings.LLM_PROVIDER.value != 'gemini':
        raise RuntimeError('Golden path requires LLM_PROVIDER=gemini')
    engine = create_async_engine(settings.DATABASE_URL)
    redis = Redis.from_url(settings.REDIS_URL)
    provider = None
    try:
        async with engine.connect() as db:
            await check_embedding_contract(db, settings)
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) == '0002_embedding_contract'
        print('PASS: PostgreSQL, migration head and vector(1536) model contract')
        assert await redis.ping()
        print('PASS: Redis')
        await asyncio.to_thread(get_s3_client(settings).head_bucket, Bucket=settings.S3_BUCKET_NAME)
        print('PASS: local S3 bucket')
        reader, writer = await asyncio.wait_for(asyncio.open_connection(settings.CLAMAV_HOST, settings.CLAMAV_PORT), 10)
        try:
            writer.write(b'zPING\0')
            await writer.drain()
            assert b'PONG' in await asyncio.wait_for(reader.read(64), 10)
        finally:
            writer.close()
            await writer.wait_closed()
        print('PASS: ClamAV')
        provider = get_llm_provider()
        assert await asyncio.wait_for(provider.health_check(), 30), 'Gemini model access failed'
        print('PASS: Gemini model metadata access (generation is checked by the real RAG test)')
    finally:
        if provider is not None:
            await provider.aclose()
        await redis.aclose()
        await engine.dispose()


if __name__ == '__main__':
    try:
        asyncio.run(check())
    except Exception as error:
        print(f'FAIL: local health ({type(error).__name__}); inspect service logs without sharing secrets', file=sys.stderr)
        raise SystemExit(1) from None
