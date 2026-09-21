"use client";

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api-client";
import { streamChatAnswer } from "@/lib/chat-stream";
import type { ChatMessage, ChatSession, Citation } from "@/types";

export function useSessions(knowledgeBaseId: string | null) {
  return useQuery({
    queryKey: ["chat-sessions", knowledgeBaseId],
    queryFn: () =>
      apiJson<ChatSession[]>(
        `/api/chat/sessions${knowledgeBaseId ? `?knowledge_base_id=${knowledgeBaseId}` : ""}`
      ),
    enabled: true,
  });
}

export function useMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ["chat-messages", sessionId],
    queryFn: () => apiJson<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`),
    enabled: !!sessionId,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { knowledgeBaseId: string; title?: string }) =>
      apiJson<ChatSession>("/api/chat/sessions", {
        method: "POST",
        body: JSON.stringify({ knowledge_base_id: params.knowledgeBaseId, title: params.title }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions"] }),
  });
}

/**
 * Manages the live streaming state for one in-flight question: the
 * partially-streamed answer text, whether we're still waiting on the first
 * token, and the citations once the stream completes. Once "done" fires,
 * the caller should invalidate the messages query so the persisted version
 * (with a real id and full citation objects) replaces this local state.
 */
export function useAskQuestion(sessionId: string | null) {
  const queryClient = useQueryClient();
  const [streamingText, setStreamingText] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const ask = useCallback(
    async (question: string) => {
      if (!sessionId) return;
      setStreamingText("");
      setStreamingCitations([]);
      setStreamError(null);
      setIsStreaming(true);

      try {
        for await (const event of streamChatAnswer(sessionId, question)) {
          if (event.type === "delta") {
            setStreamingText((prev) => prev + event.delta);
          } else if (event.type === "no_answer") {
            setStreamingText(event.delta);
          } else if (event.type === "done") {
            setStreamingCitations(event.citations as Citation[]);
          } else if (event.type === "error") {
            setStreamError(event.error || "Something went wrong while answering.");
          }
        }
      } catch (e) {
        setStreamError(e instanceof Error ? e.message : "Connection to the assistant was interrupted.");
      } finally {
        setIsStreaming(false);
        queryClient.invalidateQueries({ queryKey: ["chat-messages", sessionId] });
        queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
        queryClient.invalidateQueries({ queryKey: ["credits"] });
        queryClient.invalidateQueries({ queryKey: ["credit-usage"] });
      }
    },
    [sessionId, queryClient]
  );

  return { ask, streamingText, streamingCitations, isStreaming, streamError };
}
