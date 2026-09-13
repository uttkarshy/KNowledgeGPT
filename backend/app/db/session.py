"""Async SQLAlchemy engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # avoids stale-connection errors after RDS failover/idle
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: `db: AsyncSession = Depends(get_db)`.

    Commits on clean exit, rolls back on exception, always closes.

    Not affected by the multi-event-loop hazard below: uvicorn runs the
    entire FastAPI application under one single, long-lived event loop
    for the life of the worker process, so this engine's pool is always
    checked out and returned under the exact same loop it was created in.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Closes and discards every connection currently sitting in the
    engine's pool.

    Required by any caller that runs this SAME module-level `engine`
    across multiple, independently-created asyncio event loops - which is
    exactly what the Celery worker does: each task invocation wraps its
    work in its own `asyncio.run()` call (see
    app/workers/tasks/document_processing.py), and each `asyncio.run()`
    creates a brand-new event loop and destroys it when the call returns.

    asyncpg's connections - and the asyncio.Future objects it uses
    internally to track in-flight operations - are bound to whichever
    event loop was running at the moment they were opened. If a
    connection opened during task A's loop is still sitting in this
    shared pool when task B's separate, later `asyncio.run()` call (a
    DIFFERENT loop) checks it back out, using it raises:

        RuntimeError: Future attached to a different loop

    Calling this function at the end of a task - while that task's loop
    is still the running loop, i.e. awaited from inside the same
    `asyncio.run()` call, before it tears the loop down - closes every
    pooled connection cleanly under the loop that owns them. This
    guarantees the next task's fresh loop starts with an empty pool and
    lazily opens brand-new connections bound to itself, instead of
    inheriting stale connections/Futures from a loop that no longer
    exists.

    FastAPI's `get_db()` above does not need this: see its docstring.
    """
    await engine.dispose()