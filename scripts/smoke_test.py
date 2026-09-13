#!/usr/bin/env python3
"""Real Gemini/PDF/S3/Celery/pgvector acceptance; never substitutes mocks.

Run inside backend via scripts/start-local.ps1 -Test. Creates two disposable
accounts and leaves their data for inspection. Prints IDs, never credentials.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import secrets
import sys
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

import httpx
import fitz

sys.path.insert(0, '/app')

FACT = 'PINEAPPLE-TELESCOPE-7'
QUESTION = 'What is the secret smoke test code word?'
SECOND_QUESTION = 'What is the KnowledgeGPT test archive retention period?'
OUTSIDE = 'What is the orbital period of Neptune in Earth years?'
FILENAME = 'knowledgegpt-golden-path.pdf'


def create_pdf():
    document = fitz.open()
    for content in (
        f'KnowledgeGPT acceptance reference\n\n{QUESTION}\nThe secret smoke test code word is {FACT}.\nThis code identifies the KnowledgeGPT document processing acceptance run.',
        f'KnowledgeGPT test archive policy\n\n{SECOND_QUESTION}\nThe KnowledgeGPT test archive retention period is exactly 37 days.\nThis is a fictional test policy, not a claim about the application storage settings.',
    ):
        page = document.new_page()
        assert page.insert_textbox(fitz.Rect(50, 50, 545, 790), content, fontsize=12) >= 0
    result = document.tobytes()
    document.close()
    return result


class Acceptance:
    def __init__(self, args):
        self.args = args
        self.client = httpx.Client(base_url=args.base_url, timeout=30, trust_env=False)
        self.ids = {}
        self.citations = []
        self.tokens = {}
        self.terminals = {}

    def request(self, method, path, *, account=None, expected=200, **kwargs):
        headers = {'Authorization': f'Bearer {self.tokens[account]}'} if account else {}
        response = self.client.request(method, path, headers=headers, **kwargs)
        assert response.status_code == expected, f'{method} {path}: HTTP {response.status_code}'
        return response.json() if response.content else None

    def account(self, label):
        email = f'golden-{secrets.token_hex(8)}@example.com'
        password = secrets.token_hex(16) + 'Aa1!'
        self.request('POST', '/api/auth/register', expected=201,
                     json={'email': email, 'password': password, 'full_name': 'Golden path ' + label})
        auth = self.request('POST', '/api/auth/login', json={'email': email, 'password': password})
        self.tokens[label] = auth['access_token']
        user = self.request('GET', '/api/auth/me', account=label)
        self.ids['user_' + label] = user['id']
        kb = self.request('POST', '/api/knowledge-bases', account=label, expected=201,
                          json={'name': 'Golden path ' + label})
        self.ids['kb_' + label] = kb['id']
        session = self.request('POST', '/api/chat/sessions', account=label, expected=201,
                               json={'knowledge_base_id': kb['id']})
        self.ids['session_' + label] = session['id']

    def ask(self, account, question, **filters):
        parts, terminal = [], None
        with self.client.stream('POST', f"/api/chat/sessions/{self.ids['session_' + account]}/ask",
                headers={'Authorization': f'Bearer {self.tokens[account]}'},
                json={'question': question, **filters}, timeout=150) as response:
            assert response.status_code == 200, f'Chat HTTP {response.status_code}'
            for line in response.iter_lines():
                if not line.startswith('data:'):
                    continue
                event = json.loads(line[5:].strip())
                assert event['type'] != 'error', 'RAG returned a streaming error; inspect backend logs'
                if event['type'] == 'delta':
                    assert terminal is None, 'Stream continued after terminal event'
                    parts.append(event['delta'])
                elif event['type'] in ('done', 'no_answer'):
                    assert terminal is None, 'Multiple terminal events'
                    terminal = event
                    if event['type'] == 'no_answer':
                        parts.append(event['delta'])
        assert terminal and terminal['message_id'], 'Missing persisted terminal event'
        self.terminals[terminal['message_id']] = terminal
        return ''.join(parts), terminal

    def grounded(self, question, fact, page):
        answer, terminal = self.ask('a', question)
        assert terminal['type'] == 'done' and fact in answer, 'Expected PDF fact absent from answer'
        citations = terminal['citations']
        assert citations, 'Missing citations'
        for citation in citations:
            uuid.UUID(citation['chunk_id'])
            assert citation['document_id'] == self.ids['document']
            assert citation['document_name'] == FILENAME
            assert citation['page_number'] in (1, 2)
        assert any(c['page_number'] == page and fact in c['excerpt'] for c in citations), 'Wrong page or source excerpt'
        self.citations.extend(citations)

    async def database_evidence(self):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from app.core.config import get_settings
        from app.db.contract import check_embedding_contract
        settings = get_settings()
        assert settings.LLM_PROVIDER.value == 'gemini'
        engine = create_async_engine(settings.DATABASE_URL)
        try:
            async with engine.connect() as db:
                await check_embedding_contract(db, settings)
                rows = (await db.execute(text('''SELECT id, owner_id, knowledge_base_id, page_number,
                    content, vector_dims(embedding) AS dimensions, vector_norm(embedding) AS norm,
                    embedding_model FROM document_chunks WHERE document_id=:id'''),
                    {'id': uuid.UUID(self.ids['document'])})).mappings().all()
                assert rows and all(r['dimensions'] == 1536 and abs(r['norm'] - 1) < 0.001 for r in rows)
                assert all(r['embedding_model'] == settings.LLM_EMBEDDING_MODEL and
                           str(r['owner_id']) == self.ids['user_a'] and
                           str(r['knowledge_base_id']) == self.ids['kb_a'] for r in rows)
                by_id = {str(r['id']): r for r in rows}
                for c in self.citations:
                    row = by_id[c['chunk_id']]
                    assert row['page_number'] == c['page_number'] and c['excerpt'] in row['content']
                for message_id, terminal in self.terminals.items():
                    model = await db.scalar(text('SELECT model_used FROM chat_messages WHERE id=:id'), {'id': uuid.UUID(message_id)})
                    if terminal['type'] == 'no_answer':
                        assert model is None
                    else:
                        assert model == settings.LLM_CHAT_MODEL
                # Account B has no chunks: even a foreign document filter must retrieve nothing.
                from app.services.rag.retrieval import similarity_search, RetrievalFilters
                from app.schemas.llm import EmbeddingRequest
                from app.services.llm.factory import get_llm_provider
                provider = get_llm_provider()
                try:
                    embedding = await provider.embed(EmbeddingRequest(texts=[QUESTION], task_type='RETRIEVAL_QUERY'))
                    from sqlalchemy.ext.asyncio import AsyncSession
                    async with AsyncSession(bind=db) as session:
                        result = await similarity_search(session,
                            owner_id=uuid.UUID(self.ids['user_b']), knowledge_base_id=uuid.UUID(self.ids['kb_a']),
                            query_embedding=embedding.embeddings[0], embedding_model=settings.LLM_EMBEDDING_MODEL,
                            filters=RetrievalFilters(document_ids=[uuid.UUID(self.ids['document'])]))
                        assert result == [], 'Cross-user vector retrieval leak'
                finally:
                    await provider.aclose()
                count = await db.scalar(text("SELECT count(*) FROM api_usage_logs WHERE user_id=:id AND endpoint='rag/completion'"),
                                        {'id': uuid.UUID(self.ids['user_b'])})
                assert count == 0, 'Empty KB generated a completion'
                print(f'PASS: persisted normalized vectors, dimensions=1536, model={settings.LLM_EMBEDDING_MODEL}; citations and tenant-scoped SQL retrieval')
        finally:
            await engine.dispose()

    def run(self):
        assert self.request('GET', '/health')['status'] == 'ok'
        self.request('GET', '/api/knowledge-bases', expected=401)
        self.account('a')
        print('PASS: password registration/login and knowledge base creation')
        content = create_pdf()
        if self.args.pdf_output:
            Path(self.args.pdf_output).write_bytes(content)
        upload = self.request('POST', '/api/documents/upload-url', account='a', expected=201, json={
            'knowledge_base_id': self.ids['kb_a'], 'filename': FILENAME,
            'content_type': 'application/pdf', 'size_bytes': len(content)})
        self.ids['document'] = upload['document_id']
        url = upload['upload_url']
        headers = {'Content-Type': 'application/pdf'}
        if self.args.s3_transport_url:
            public, internal = urlsplit(url), urlsplit(self.args.s3_transport_url)
            # Connect within Compose while preserving the signed Host header.
            # No presigned URL is ever printed. Browser PUT is checked separately.
            headers['Host'] = public.netloc
            url = urlunsplit((internal.scheme, internal.netloc, public.path, public.query, ''))
        with httpx.Client(timeout=30, trust_env=False) as storage:
            response = storage.put(url, content=content, headers=headers)
            assert response.status_code in (200, 204), f'S3 PUT HTTP {response.status_code}'
            # HEAD through the same internal storage client proves actual persistence before enqueue.
        if self.args.verify_database:
            from app.core.aws import head_object_size
            from app.core.config import get_settings
            assert head_object_size(settings=get_settings(), key=upload['s3_key']) == len(content)
        self.request('POST', '/api/documents/confirm', account='a', json={'document_id': self.ids['document']})
        print('PASS: real two-page PDF uploaded to storage and confirmed for Celery')
        deadline = time.monotonic() + self.args.processing_timeout
        last = None
        while time.monotonic() < deadline:
            doc = self.request('GET', f"/api/documents/{self.ids['document']}/status", account='a')
            if doc['status'] != last:
                last = doc['status']
                print(f'Processing: {last} ({doc["processing_progress_pct"]}%)', flush=True)
            assert doc['status'] != 'failed', 'Document FAILED; inspect Celery logs for failure category'
            if doc['status'] == 'completed':
                assert doc['processing_progress_pct'] == 100
                break
            time.sleep(2)
        else:
            raise AssertionError('Document processing deadline exceeded')
        docs = self.request('GET', '/api/documents', account='a', params={'knowledge_base_id': self.ids['kb_a']})
        stored = next(d for d in docs if d['id'] == self.ids['document'])
        assert stored['page_count'] == 2 and stored['chunk_count'] >= 2
        self.grounded(QUESTION, FACT, 1)
        self.grounded(SECOND_QUESTION, '37', 2)
        print('PASS: real Gemini streamed answers with correct facts, page/excerpt/chunk citations and second turn')
        answer, terminal = self.ask('a', OUTSIDE)
        assert terminal['type'] == 'no_answer' and not terminal.get('citations'), 'Out-of-scope question failed no-answer gate'
        print('PASS: out-of-scope question returns structural no-answer')
        self.account('b')
        for path in (f"/api/knowledge-bases/{self.ids['kb_a']}", f"/api/documents/{self.ids['document']}/status",
                     f"/api/chat/sessions/{self.ids['session_a']}/messages"):
            self.request('GET', path, account='b', expected=404)
        self.request('POST', '/api/documents/confirm', account='b', expected=404, json={'document_id': self.ids['document']})
        self.request('POST', '/api/chat/sessions', account='b', expected=404, json={'knowledge_base_id': self.ids['kb_a']})
        answer, terminal = self.ask('b', QUESTION, document_ids=[self.ids['document']])
        assert terminal['type'] == 'no_answer' and FACT not in answer and not terminal.get('citations')
        self.request('GET', '/health/deep', account='b', expected=403)
        print('PASS: second account cannot read foreign KB, document, chat, citations or vectors')
        for label in ('a', 'b'):
            messages = self.request('GET', f"/api/chat/sessions/{self.ids['session_' + label]}/messages", account=label)
            for message in (m for m in messages if m['role'] == 'assistant'):
                terminal = self.terminals[message['id']]
                assert {c['chunk_id'] for c in message['citations']} == {c['chunk_id'] for c in terminal.get('citations', [])}
        print('PASS: messages and citations persist across fresh HTTP reads')
        if self.args.verify_database:
            asyncio.run(self.database_evidence())
        else:
            raise AssertionError('Database evidence required; rerun inside backend with --verify-database')
        print('REAL API RAG ACCEPTANCE: PASS. Browser upload/render/refresh still requires the documented UI check.')
        print('Evidence IDs: ' + json.dumps(self.ids, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--s3-transport-url')
    parser.add_argument('--processing-timeout', type=int, default=900)
    parser.add_argument('--verify-database', action='store_true')
    parser.add_argument('--pdf-output')
    args = parser.parse_args()
    test = Acceptance(args)
    try:
        test.run()
    except (AssertionError, httpx.HTTPError) as error:
        # httpx exception strings can contain signed URLs, so never print those.
        reason = str(error) if isinstance(error, AssertionError) else type(error).__name__
        print(f'REAL RAG ACCEPTANCE: FAIL: {reason}', file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:
        print(f'REAL RAG ACCEPTANCE: FAIL ({type(error).__name__}); inspect local service logs', file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        test.client.close()


if __name__ == '__main__':
    main()
