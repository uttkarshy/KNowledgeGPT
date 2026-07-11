"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { SessionRail } from "@/components/chat/session-rail";
import { SourcesRail } from "@/components/chat/sources-rail";
import { useAskQuestion, useCreateSession, useMessages, useSessions } from "@/hooks/use-chat";
import type { Citation } from "@/types";

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-mist-50 dark:bg-ink-950">
          <p className="text-sm text-ink-500">Loading…</p>
        </main>
      }
    >
      <ChatPageInner />
    </Suspense>
  );
}

function ChatPageInner() {
  const searchParams = useSearchParams();
  // In a full app this comes from a knowledge-base picker; for this
  // increment we read it from the URL (?kb=<id>) since KB
  // creation/selection UI is a separate Dashboard increment.
  const knowledgeBaseId = searchParams.get("kb");

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeCitationIndex, setActiveCitationIndex] = useState<number | null>(null);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: sessions = [] } = useSessions(knowledgeBaseId);
  const { data: messages = [] } = useMessages(activeSessionId);
  const createSession = useCreateSession();
  const { ask, streamingText, streamingCitations, isStreaming, streamError } = useAskQuestion(activeSessionId);

  useEffect(() => {
    if (!activeSessionId && sessions.length > 0) {
      setActiveSessionId(sessions[0]?.id ?? null);
    }
  }, [sessions, activeSessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingText]);

  useEffect(() => {
    if (streamingCitations.length > 0) setLastCitations(streamingCitations);
  }, [streamingCitations]);

  const handleCreateNew = async () => {
    if (!knowledgeBaseId) return;
    const session = await createSession.mutateAsync({ knowledgeBaseId });
    setActiveSessionId(session.id);
  };

  const handleSend = (question: string) => {
    setActiveCitationIndex(null);
    ask(question);
  };

  const handleCitationClick = (index: number) => {
    setActiveCitationIndex(index);
    document
      .getElementById(`source-card-${index}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const lastMessageCitations = messages.length > 0 ? messages[messages.length - 1]?.citations ?? [] : [];
  const displayedCitations = lastCitations.length > 0 ? lastCitations : lastMessageCitations;

  if (!knowledgeBaseId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-mist-50 dark:bg-ink-950">
        <p className="text-sm text-ink-500">
          Select a knowledge base from the dashboard to start chatting.
        </p>
      </main>
    );
  }

  return (
    <div className="flex h-screen bg-mist-50 dark:bg-ink-950">
      <SessionRail
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={setActiveSessionId}
        onCreateNew={handleCreateNew}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-6 scrollbar-thin">
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              role={message.role === "user" ? "user" : "assistant"}
              content={message.content}
              citations={message.citations}
              modelUsed={message.model_used}
              latencyMs={message.latency_ms}
              inputTokens={message.input_tokens}
              outputTokens={message.output_tokens}
              activeCitationIndex={activeCitationIndex}
              onCitationClick={handleCitationClick}
            />
          ))}

          {isStreaming && (
            <MessageBubble
              role="assistant"
              content={streamingText || "…"}
              citations={streamingCitations}
              activeCitationIndex={activeCitationIndex}
              onCitationClick={handleCitationClick}
            />
          )}

          {streamError && (
            <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {streamError}
            </p>
          )}

          {messages.length === 0 && !isStreaming && (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-ink-500">
                Ask a question to get started. Answers are grounded only in your uploaded documents.
              </p>
            </div>
          )}
        </div>

        <ChatInput onSend={handleSend} disabled={isStreaming || !activeSessionId} />
      </div>

      <SourcesRail citations={displayedCitations} activeIndex={activeCitationIndex} />
    </div>
  );
}
