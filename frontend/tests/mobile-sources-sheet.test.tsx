import assert from 'node:assert/strict';
import test from 'node:test';
import React, { act } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { MessageBubble } from '../src/components/chat/message-bubble';
import { MobileSourcesSheet } from '../src/components/chat/mobile-sources-sheet';
import type { Citation } from '../src/types';

const citation = {
  chunk_id: 'chunk-1',
  document_id: 'doc-1',
  document_name: 'Evidence.pdf',
  page_number: 2,
  section: 'Summary',
  excerpt: 'Grounded evidence excerpt.',
  similarity_score: 0.91,
} satisfies Citation;

test('assistant with citations renders compact mobile sources control', () => {
  const html = renderToStaticMarkup(
    <MessageBubble role="assistant" content="Answer [1]" citations={[citation]}
      activeCitationIndex={null} onCitationClick={() => {}} onViewSources={() => {}} />,
  );
  const doc = new JSDOM(html).window.document;
  const button = doc.querySelector('button[aria-label="View 1 source"]');
  assert.equal(button?.textContent?.trim(), 'View 1 source');
  assert.ok(button?.className.includes('lg:hidden'));
});

test('mobile sources sheet reuses evidence content and closes cleanly', async () => {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  const root = createRoot(dom.window.document.getElementById('root')!);
  let closed = 0;
  try {
    await act(async () => root.render(
      <MobileSourcesSheet open citations={[citation]} activeIndex={1} onClose={() => { closed += 1; }} />,
    ));
    assert.equal(dom.window.document.querySelector('[role="dialog"]')?.getAttribute('aria-label'), 'Evidence');
    assert.equal(dom.window.document.querySelector('#mobile-source-card-1')?.textContent?.includes('Grounded evidence excerpt.'), true);
    const closeButton = dom.window.document.querySelector('button[aria-label="Close evidence"]') as HTMLButtonElement;
    await act(async () => closeButton.click());
    assert.equal(closed, 1);
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
  }
});
