"""Isolated acceptance flow. Run explicitly with the QA dependencies listed in docs/mobile/testing.md."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from unittest.mock import AsyncMock, patch

import fitz
import httpx
from embedded_postgres._commands import POSTGRES_BIN_PATH
from moto.server import ThreadedMotoServer

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def exercise():
    from app.api import support
    from app.core.aws import get_s3_client
    from app.core.config import get_settings
    from app.db.session import engine
    from app.main import app
    from app.schemas.llm import EmbeddingResult, LLMStreamChunk
    from app.services.llm import get_llm_provider
    from app.workers.tasks.document_processing import (
        process_document,
        process_document_async,
    )

    phrase = "The archive opens every Tuesday at nine."

    class FixtureModel:
        async def embed(self, req):
            return EmbeddingResult(
                embeddings=[[1.0] + [0.0] * 7 for _ in req.texts],
                model="fixture",
                dimensions=8,
            )

        async def stream(self, req):
            assert phrase in req.messages[-1].content
            yield LLMStreamChunk(delta=phrase + " [1]")
            yield LLMStreamChunk(done=True)

    provider = FixtureModel()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    settings = get_settings()
    get_s3_client(settings).create_bucket(Bucket=settings.S3_BUCKET_NAME)
    queued = []
    password = "Fixture9!" + secrets.token_hex(8)
    with (
        patch.object(process_document, "delay", side_effect=queued.append),
        patch("app.services.llm.factory.get_llm_provider", return_value=provider),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://fixture.local"
        ) as c:

            async def call(method, path, code=200, body=None, headers=None):
                r = await c.request(method, "/api/" + path, json=body, headers=headers)
                assert r.status_code == code, (path, r.status_code)
                return r.json() if r.content else None

            async def identity(email):
                await call(
                    "POST", "auth/register", 201, {"email": email, "password": password}
                )
                pair = await call(
                    "POST", "auth/login", body={"email": email, "password": password}
                )
                return {"Authorization": "Bearer " + pair["access_token"]}, pair[
                    "refresh_token"
                ]

            owner, renewal = await identity("reader@example.com")
            other, _ = await identity("other@example.com")
            assert (await call("GET", "auth/me", headers=owner))[
                "email"
            ] == "reader@example.com"
            kb = (
                await call("POST", "knowledge-bases", 201, {"name": "Archive"}, owner)
            )["id"]
            print("PASS registration, login and knowledge-base creation")
            with fitz.open() as pdf:
                pdf.new_page().insert_text((72, 72), phrase)
                data = pdf.tobytes()
            up = await call(
                "POST",
                "documents/upload-url",
                201,
                {
                    "knowledge_base_id": kb,
                    "filename": "archive.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": len(data),
                },
                owner,
            )
            async with httpx.AsyncClient(trust_env=False) as storage:
                put = await storage.put(
                    up["upload_url"],
                    content=data,
                    headers={"Content-Type": "application/pdf"},
                )
                assert put.status_code == 200
            did = up["document_id"]
            await call(
                "POST", "documents/confirm", body={"document_id": did}, headers=owner
            )
            assert queued == [did]
            await process_document_async(process_document, did)
            assert (await call("GET", "documents/" + did + "/status", headers=owner))[
                "status"
            ] == "completed"
            print(
                "PASS presigned PUT, confirm, PDF extraction, indexing and processing status"
            )
            sid = (
                await call(
                    "POST", "chat/sessions", 201, {"knowledge_base_id": kb}, owner
                )
            )["id"]
            stream = await c.post(
                "/api/chat/sessions/" + sid + "/ask",
                json={"question": "When does the archive open?"},
                headers=owner,
            )
            events = [
                json.loads(v[6:])
                for v in stream.text.splitlines()
                if v.startswith("data: ")
            ]
            assert (
                events[-1]["type"] == "done"
                and events[-1]["citations"][0]["document_id"] == did
            )
            assert events[-1]["citations"][0]["page_number"] == 1
            history = "chat/sessions/" + sid + "/messages"
            saved = await call("GET", history, headers=owner)
            assert (
                len(saved) == 2
                and saved[-1]["content"].endswith("[1]")
                and phrase in saved[-1]["citations"][0]["excerpt"]
            )
            print(
                "PASS pgvector retrieval, streamed fixture answer and persisted page citation"
            )
            await call("GET", history, 404, headers=other)
            await call("GET", "documents/" + did + "/status", 404, headers=other)
            assert await call("GET", "knowledge-bases", headers=other) == []
            assert await call("GET", "documents", headers=other) == []
            rotated = await call(
                "POST", "auth/refresh", body={"refresh_token": renewal}
            )
            await call(
                "POST", "auth/logout", 204, {"refresh_token": rotated["refresh_token"]}
            )
            await call(
                "POST", "auth/refresh", 401, {"refresh_token": rotated["refresh_token"]}
            )
            signed = await call(
                "POST",
                "auth/login",
                body={"email": "reader@example.com", "password": password},
            )
            owner = {"Authorization": "Bearer " + signed["access_token"]}
            assert (await call("GET", history, headers=owner))[-1]["id"] == saved[-1][
                "id"
            ]
            print(
                "PASS owner isolation, rotation, logout, re-login and history recovery"
            )
            report = {"message_id": saved[-1]["id"], "reason": "Synthetic report"}
            await call("POST", "support/report-answer", 404, report, other)
            await call("POST", "support/report-answer", 503, report, owner)
            with patch.object(
                support.aiosmtplib, "send", AsyncMock(return_value=({}, "accepted"))
            ) as mail:
                settings.SMTP_HOST = "localhost"
                settings.SUPPORT_INBOX = "support@example.com"
                assert (
                    await call("POST", "support/report-answer", 202, report, owner)
                )["reference"]
                assert (
                    await call(
                        "POST",
                        "support/deletion-request",
                        202,
                        {"email": "reader@example.com", "confirmation": "DELETE"},
                    )
                )["reference"]
                assert mail.await_count == 2
            await call("DELETE", "documents/" + did, 204, headers=owner)
            print(
                "PASS reporting ownership, delivery errors and simulated receipts, document deletion"
            )
    await engine.dispose()


def main():
    with tempfile.TemporaryDirectory(prefix="kg-mobile-qa-") as td:
        db = str(Path(td) / "db")
        port, s3port = available_port(), available_port()
        subprocess.run(
            [
                str(POSTGRES_BIN_PATH / "initdb"),
                "-D",
                db,
                "-U",
                "postgres",
                "-A",
                "trust",
                "--no-locale",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        server = subprocess.Popen(
            [
                str(POSTGRES_BIN_PATH / "postgres"),
                "-D",
                db,
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-c",
                "unix_socket_directories=",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import redislite

        redis_port = available_port()
        binary = Path(redislite.__file__).parent / "bin" / "redis-server"
        cache = subprocess.Popen(
            [
                str(binary),
                "--bind",
                "127.0.0.1",
                "--port",
                str(redis_port),
                "--save",
                "",
                "--appendonly",
                "no",
                "--dir",
                td,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.environ["REDIS_URL"] = f"redis://127.0.0.1:{redis_port}/0"
        s3 = ThreadedMotoServer(ip_address="127.0.0.1", port=s3port, verbose=False)
        try:
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.1)
            os.environ.update(
                DATABASE_URL=f"postgresql+asyncpg://postgres@127.0.0.1:{port}/postgres",
                JWT_SECRET_KEY=secrets.token_hex(32),
                LLM_EMBEDDING_DIMENSIONS="8",
                VIRUS_SCAN_ENABLED="false",
                AWS_ACCESS_KEY_ID="fixture",
                AWS_SECRET_ACCESS_KEY="fixture",
                AWS_S3_ENDPOINT_URL=f"http://127.0.0.1:{s3port}",
                AWS_EC2_METADATA_DISABLED="true",
                NO_PROXY="127.0.0.1,localhost",
                no_proxy="127.0.0.1,localhost",
                SMTP_HOST="",
                SUPPORT_INBOX="",
            )
            s3.start()
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=BACKEND,
                check=True,
            )
            print("PASS fresh PostgreSQL and pgvector migration")
            asyncio.run(exercise())
        finally:
            s3.stop()
            cache.terminate()
            cache.wait(timeout=10)
            server.terminate()
            server.wait(timeout=15)


if __name__ == "__main__":
    main()
