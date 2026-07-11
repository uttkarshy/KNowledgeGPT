#!/bin/sh
set -e

echo "Waiting for database..."
python3 - <<'PYEOF'
import asyncio
import sys
import time

from app.core.config import get_settings

async def wait_for_db():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("Database is ready.")
            await engine.dispose()
            return
        except Exception as e:  # noqa: BLE001
            print(f"Database not ready (attempt {attempt}/{max_attempts}): {e}")
            time.sleep(2)
    print("Database never became ready — exiting.")
    sys.exit(1)

asyncio.run(wait_for_db())
PYEOF

# Only the API container runs migrations (RUN_MIGRATIONS=true in
# docker-compose for that service only) — the Celery worker container
# shares this same entrypoint/image but shouldn't race the API container to
# apply migrations concurrently.
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

echo "Starting: $@"
exec "$@"
