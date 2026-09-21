/**
 * Consumes a `text/event-stream` response from a POST request.
 *
 * The browser's native EventSource API only supports GET requests, but our
 * /api/chat/sessions/{id}/ask endpoint is POST (it has a JSON body), so we
 * parse the SSE frames manually from the fetch Response's ReadableStream
 * instead.
 */

import { apiFetch } from "@/lib/api-client";

export interface ChatStreamEvent {
  type: "delta" | "no_answer" | "done" | "error";
  delta: string;
  message_id: string | null;
  citations: Array<{
    chunk_id: string;
    document_id: string;
    document_name: string;
    page_number: number | null;
    section: string | null;
    similarity_score: number;
    excerpt: string;
  }>;
  confidence: number | null;
  error: string | null;
}

export async function* streamChatAnswer(
  sessionId: string,
  question: string,
  options?: { documentIds?: string[]; language?: string; signal?: AbortSignal }
): AsyncGenerator<ChatStreamEvent> {
  const response = await apiFetch(`/api/chat/sessions/${sessionId}/ask`, {
    method: "POST",
    body: JSON.stringify({
      question,
      document_ids: options?.documentIds,
      language: options?.language,
    }),
    signal: options?.signal,
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });

  if (!response.ok || !response.body) {
    let detail = `Chat stream request failed: ${response.status}`;
    try { detail = String((await response.json()).detail || detail); } catch { /* non-JSON */ }
    throw new Error(detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  let terminal = false;
  try {
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? ""; // last (possibly incomplete) frame stays in the buffer

    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const jsonStr = line.slice("data:".length).trim();
      if (!jsonStr) continue;
      try {
        const event = JSON.parse(jsonStr) as ChatStreamEvent;
        if (["done", "no_answer", "error"].includes(event.type)) terminal = true;
        yield event;
      } catch {
        throw new Error("The answer stream was invalid. Please retry.");
      }
    }
  }
  if (!terminal) throw new Error("The answer was interrupted before it could be saved. Please retry.");
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
