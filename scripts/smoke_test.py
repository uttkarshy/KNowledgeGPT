#!/usr/bin/env python3
"""
End-to-end smoke test for a deployed KnowledgeGPT environment.

This is the real final-deployment check — run it against your actual
deployed URL (local Docker Compose or production) after `terraform apply`
or `docker compose up` to confirm the whole pipeline genuinely works,
rather than trusting that each piece works in isolation.

Usage:
    pip install httpx
    python scripts/smoke_test.py --base-url http://localhost:8000

Requires a real, working OpenAI API key configured on the target
environment — this test asks a real question and expects a real,
grounded, cited answer back. It is NOT safe to run against a shared
production environment without expecting to create a throwaway test user,
knowledge base, and document there.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time

import httpx

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


class SmokeTestFailure(Exception):
    pass


def step(description: str):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            print(f"  {description} ... ", end="", flush=True)
            try:
                result = fn(*args, **kwargs)
                print(PASS)
                return result
            except Exception as e:
                print(FAIL)
                raise SmokeTestFailure(f"{description}: {e}") from e

        return wrapper

    return decorator


class SmokeTest:
    def __init__(self, base_url: str):
        self.client = httpx.Client(base_url=base_url, timeout=30.0)
        self.email = f"smoketest+{secrets.token_hex(4)}@example.com"
        self.password = "SmokeTest123!@#"
        self.access_token: str | None = None
        self.kb_id: str | None = None
        self.session_id: str | None = None
        self.document_id: str | None = None

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    @step("Health check")
    def check_health(self):
        r = self.client.get("/health")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ok"

    @step("Deep health check (database + Redis reachable)")
    def check_deep_health(self):
        r = self.client.get("/health/deep")
        body = r.json()
        assert body["checks"].get("database") == "ok", body
        assert body["checks"].get("redis") == "ok", body

    @step("Register a test user")
    def register(self):
        r = self.client.post(
            "/api/auth/register",
            json={"email": self.email, "password": self.password, "full_name": "Smoke Test"},
        )
        assert r.status_code == 201, r.text

    @step("Log in")
    def login(self):
        r = self.client.post("/api/auth/login", json={"email": self.email, "password": self.password})
        assert r.status_code == 200, r.text
        self.access_token = r.json()["access_token"]

    @step("Create a knowledge base")
    def create_knowledge_base(self):
        r = self.client.post(
            "/api/knowledge-bases", json={"name": "Smoke Test KB"}, headers=self._auth_headers()
        )
        assert r.status_code == 201, r.text
        self.kb_id = r.json()["id"]

    @step("Upload a small text document (presigned URL -> S3 PUT -> confirm)")
    def upload_document(self):
        content = (
            b"KnowledgeGPT Smoke Test Document\n\n"
            b"The secret smoke test code word is PINEAPPLE-TELESCOPE-7. "
            b"This document exists solely to verify the upload and RAG pipeline end to end."
        )
        r = self.client.post(
            "/api/documents/upload-url",
            json={
                "knowledge_base_id": self.kb_id,
                "filename": "smoke_test.txt",
                "content_type": "text/plain",
                "size_bytes": len(content),
            },
            headers=self._auth_headers(),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        self.document_id = body["document_id"]

        put_response = httpx.put(body["upload_url"], content=content, headers={"Content-Type": "text/plain"})
        assert put_response.status_code in (200, 204), put_response.text

        confirm = self.client.post(
            "/api/documents/confirm", json={"document_id": self.document_id}, headers=self._auth_headers()
        )
        assert confirm.status_code == 200, confirm.text

    @step("Wait for the document to finish processing (up to 2 minutes)")
    def wait_for_processing(self):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            r = self.client.get(f"/api/documents/{self.document_id}/status", headers=self._auth_headers())
            status = r.json()["status"]
            if status == "completed":
                return
            if status == "failed":
                raise AssertionError(f"Document processing failed: {r.json().get('status_detail')}")
            time.sleep(3)
        raise AssertionError("Document did not finish processing within 2 minutes")

    @step("Create a chat session")
    def create_chat_session(self):
        r = self.client.post(
            "/api/chat/sessions", json={"knowledge_base_id": self.kb_id}, headers=self._auth_headers()
        )
        assert r.status_code == 201, r.text
        self.session_id = r.json()["id"]

    @step("Ask a grounded question and confirm a cited, streamed answer")
    def ask_grounded_question(self):
        full_text = ""
        citations = []
        with self.client.stream(
            "POST",
            f"/api/chat/sessions/{self.session_id}/ask",
            json={"question": "What is the secret smoke test code word?"},
            headers=self._auth_headers(),
            timeout=60.0,
        ) as response:
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):].strip())
                if event["type"] == "delta":
                    full_text += event["delta"]
                elif event["type"] == "done":
                    citations = event["citations"]

        assert "PINEAPPLE-TELESCOPE-7" in full_text, f"Answer did not contain the expected fact: {full_text!r}"
        assert len(citations) > 0, "Expected at least one citation for a grounded answer"

    @step("Ask an ungrounded question and confirm it correctly refuses to guess")
    def ask_ungrounded_question(self):
        full_text = ""
        with self.client.stream(
            "POST",
            f"/api/chat/sessions/{self.session_id}/ask",
            json={"question": "What is the capital of France?"},
            headers=self._auth_headers(),
            timeout=60.0,
        ) as response:
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):].strip())
                if event["type"] in ("delta", "no_answer"):
                    full_text += event["delta"]

        assert "couldn't find" in full_text.lower() or "don't have" in full_text.lower(), (
            f"Expected a refusal for an out-of-context question, got: {full_text!r}"
        )

    def run(self):
        print(f"Running smoke test against {self.client.base_url}\n")
        self.check_health()
        self.check_deep_health()
        self.register()
        self.login()
        self.create_knowledge_base()
        self.upload_document()
        self.wait_for_processing()
        self.create_chat_session()
        self.ask_grounded_question()
        self.ask_ungrounded_question()
        print("\nAll smoke test steps passed. The pipeline works end to end.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the backend API")
    args = parser.parse_args()

    test = SmokeTest(args.base_url)
    try:
        test.run()
    except SmokeTestFailure as e:
        print(f"\nSMOKE TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
