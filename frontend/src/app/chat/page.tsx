"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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
  const router = useRouter();
  const knowledgeBaseId = searchParams.get("kb");

  const [activeSessionId, setActiveSessionId] = useState<string | null>(searchParams.get("session"));
  const [activeCitationIndex, setActiveCitationIndex] = useState<number | null>(null);
  const [lastCitations, setLastCitations] = useState<Citation[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: sessions = [], error: sessionsError } = useSessions(knowledgeBaseId);
  const { data: messages = [], error: messagesError, isLoading: messagesLoading } = useMessages(activeSessionId);
  const createSession = useCreateSession();
  const { ask, streamingText, streamingCitations, isStreaming, streamError } = useAskQuestion(activeSessionId);

  useEffect(() => {
    if (!activeSessionId && sessions.length > 0) {
      setActiveSessionId(sessions[0]?.id ?? null);
    }
  }, [sessions, activeSessionId]);

  useEffect(() => {
    setLastCitations([]);
    setActiveCitationIndex(null);
    if (activeSessionId && knowledgeBaseId) router.replace(`/chat?kb=${knowledgeBaseId}&session=${activeSessionId}`, { scroll: false });
  }, [activeSessionId, knowledgeBaseId, router]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingText]);

  useEffect(() => {
    if (streamingCitations.length > 0) setLastCitations(streamingCitations);
  }, [streamingCitations]);

  const handleCreateNew = async () => {
    if (!knowledgeBaseId) return;
    try {
      const session = await createSession.mutateAsync({ knowledgeBaseId });
      setActiveSessionId(session.id);
    } catch { /* mutation error is shown below */ }
  };

  const handleSend = (question: string) => {
    setLastCitations([]);
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
          <Link href="/dashboard" className="text-stamp-teal underline">Select a knowledge base from the dashboard to start chatting.</Link>
        </p>
      </main>
    );
  }

  return (
    <div className="flex h-dvh flex-col lg:flex-row bg-mist-50 dark:bg-ink-950">
      <SessionRail
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={setActiveSessionId}
        onCreateNew={handleCreateNew}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <Link href="/dashboard" className="border-b px-4 py-2 text-sm text-stamp-teal">← Knowledge bases</Link>
        {(sessionsError || messagesError || createSession.error) && <p role="alert" className="p-3 text-danger">{(sessionsError || messagesError || createSession.error)?.message}</p>}
        {messagesLoading && <p className="p-3">Loading conversation…</p>}
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
              onCitationClick={(index) => { setLastCitations(message.citations); handleCitationClick(index); }}
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
                Choose New chat to begin, then ask a question about your documents.
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
