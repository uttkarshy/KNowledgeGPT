import assert from 'node:assert/strict';
import test from 'node:test';
import React, { act } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import { MessageContent } from '../src/components/chat/message-content';
import type { Citation } from '../src/types';

const citations = Array.from({ length: 6 }, () => ({} as Citation));
function render(content: string) {
  return new JSDOM(renderToStaticMarkup(<MessageContent content={content} citations={citations}
    activeCitationIndex={null} onCitationClick={() => {}} />)).window.document;
}

test('citations preserve bold spans and paragraph structure', () => {
  const doc = render('**Total [6] is 1715.89**\n\n**Second [2] claim**');
  assert.equal(doc.querySelectorAll('strong').length, 2);
  assert.equal(doc.querySelectorAll('p').length, 2);
  assert.equal(doc.querySelector('strong button')?.getAttribute('aria-label'), 'View source 6');
  assert.ok(!doc.body.textContent?.includes('**'));
});

test('citations stay within parsed GFM table cells', () => {
  const doc = render('| Amount | Source |\n| --- | --- |\n| **309** | [2] |');
  assert.equal(doc.querySelectorAll('table').length, 1);
  assert.equal(doc.querySelector('td button')?.textContent, '2');
  assert.equal(doc.querySelector('td strong')?.textContent, '309');
});

test('code, links, and invalid markers remain intact', () => {
  const doc = render('`[1]`\n\n```text\n[2]\n```\n\n[[3]](https://example.com) and [99]');
  assert.equal(doc.querySelectorAll('button').length, 0);
  assert.equal(doc.querySelector('a')?.textContent, '[3]');
  assert.ok(doc.querySelector('pre')?.textContent?.includes('[2]'));
  assert.ok(doc.body.textContent?.includes('[99]'));
});

test('click navigates using the original one-based source number', async () => {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost' });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  const root = createRoot(dom.window.document.getElementById('root')!);
  let selected = 0;
  try {
    await act(async () => root.render(<MessageContent content='**Source [2]**' citations={citations}
      activeCitationIndex={2} onCitationClick={(index) => { selected = index; }} />));
    const button = dom.window.document.querySelector('button')!;
    assert.ok(button.className.includes('ring-2'));
    await act(async () => button.click());
    assert.equal(selected, 2);
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
  }
});
