import assert from 'node:assert/strict';
import test from 'node:test';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DocumentsPanel } from '../src/components/dashboard/documents-panel';

test('configured page limits and Retry Processing resume without another upload', async () => {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document,
    localStorage: dom.window.localStorage, IS_REACT_ACT_ENVIRONMENT: true });
  const previousFetch = globalThis.fetch;
  const calls: string[] = [];
  let retried = false;
  const doc = () => ({ id: 'synthetic', knowledge_base_id: 'kb', name: 'synthetic.pdf', file_type: 'pdf',
    status: retried ? 'virus_scanning' : 'failed', status_detail: 'AI processing temporarily rate-limited.',
    retryable: !retried, processing_progress_pct: 60, chunk_count: 0, original_size_bytes: 1000 });
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    calls.push(`${init?.method || 'GET'} ${url}`);
    if (url.endsWith('/retry')) { retried = true; return Response.json(doc()); }
    if (url.endsWith('/limits')) return Response.json({ max_size_bytes: 1048576, max_pdf_pages: 37, allowed_extensions: ['pdf'] });
    if (url.includes('/api/documents?')) return Response.json([doc()]);
    throw new Error('Unexpected request');
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const root = createRoot(dom.window.document.getElementById('root')!);
  async function waitFor(check: () => boolean) {
    for (let i = 0; i < 50; i++) {
      await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
      if (check()) return;
    }
    assert.fail('UI did not reach expected state');
  }
  try {
    await act(async () => root.render(<QueryClientProvider client={client}><DocumentsPanel knowledgeBaseId="kb" onClose={() => {}} /></QueryClientProvider>));
    await waitFor(() => dom.window.document.body.textContent!.includes('37 pages'));
    assert.ok(!dom.window.document.body.textContent!.includes('25 MB'));
    const button = Array.from(dom.window.document.querySelectorAll('button')).find(b => b.textContent === 'Retry Processing');
    assert.ok(button);
    await act(async () => button.click());
    await waitFor(() => !dom.window.document.body.textContent!.includes('Retry Processing'));
    assert.equal(calls.filter(c => c.startsWith('POST')).length, 1);
    assert.ok(calls.some(c => c.endsWith('/api/documents/synthetic/retry')));
    assert.ok(!calls.some(c => c.includes('upload-url')));
  } finally {
    await act(async () => root.unmount());
    client.clear(); globalThis.fetch = previousFetch; dom.window.close();
  }
});
