import asyncio
import uuid
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse

from app.core import usage_logging


@pytest.mark.parametrize('streaming', [False, True])
async def test_single_connection_pool_request_cleanup_before_telemetry(monkeypatch, streaming):
    pool = asyncio.Semaphore(1)
    rows = []
    order = []

    class Session:
        def add(self, row):
            rows.append(row)

        async def commit(self):
            order.append('log')

    @asynccontextmanager
    async def sessions():
        async with pool:
            yield Session()

    async def request_db():
        async with pool:
            try:
                yield
            finally:
                order.append('cleanup')

    app = FastAPI()
    app.add_middleware(usage_logging.ApiUsageLoggingMiddleware)
    monkeypatch.setattr(usage_logging, 'AsyncSessionLocal', sessions)
    monkeypatch.setattr(usage_logging, '_extract_user_id', lambda request: uuid.uuid4())

    @app.get('/test')
    async def endpoint(db=Depends(request_db)):
        if streaming:
            async def body():
                yield 'first'
                await asyncio.sleep(0)
                yield 'last'
            return StreamingResponse(body())
        return {'ok': True}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        for _ in range(25):
            result = await asyncio.wait_for(client.get('/test'), 2)
            assert result.status_code == 200
            assert not pool.locked()
        await client.get('/health')
    assert len(rows) == 25
    assert order == ['cleanup', 'log'] * 25
    assert all(r.endpoint == '/test' and r.status_code == 200 and r.latency_ms >= 0 for r in rows)


async def test_telemetry_failure_does_not_break_response(monkeypatch):
    @asynccontextmanager
    async def broken():
        raise RuntimeError('database unavailable')
        yield

    app = FastAPI()
    app.add_middleware(usage_logging.ApiUsageLoggingMiddleware)
    monkeypatch.setattr(usage_logging, 'AsyncSessionLocal', broken)
    monkeypatch.setattr(usage_logging, '_extract_user_id', lambda request: uuid.uuid4())

    @app.get('/test')
    async def endpoint():
        return {'ok': True}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/test')).json() == {'ok': True}
