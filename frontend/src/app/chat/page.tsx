"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { ArrowLeft, BookOpen, Coins, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { SessionRail } from "@/components/chat/session-rail";
import { SourcesRail } from "@/components/chat/sources-rail";
import { useAskQuestion, useCreateSession, useMessages, useSessions } from "@/hooks/use-chat";
import type { Citation } from "@/types";
import { Brand } from "@/components/brand";
import { SignOutButton } from "@/components/sign-out-button";
import { useKnowledgeBases } from "@/hooks/use-knowledge-bases";
import { useCredits } from "@/hooks/use-billing";

const STARTER_QUESTIONS = [
  "Summarize the key points",
  "What are the most important dates?",
  "Which sections should I read first?",
];

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
  const { data: knowledgeBases = [] } = useKnowledgeBases();
  const credits = useCredits();
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
  const knowledgeBase = knowledgeBases.find((kb) => kb.id === knowledgeBaseId);

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
    <div className="flex h-dvh flex-col overflow-hidden bg-canvas dark:bg-ink-950">
      <header className="z-20 flex h-16 shrink-0 items-center justify-between border-b border-ink-950/[0.07] bg-white/85 px-3 backdrop-blur-xl dark:border-white/10 dark:bg-ink-900/85 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/dashboard" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-ink-500 transition hover:bg-mist-50 hover:text-ink-950 dark:hover:bg-ink-800" aria-label="Back to knowledge bases"><ArrowLeft size={18} /></Link>
          <div className="hidden sm:block"><Brand /></div>
          <span className="hidden h-6 w-px bg-ink-950/10 sm:block dark:bg-white/10" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-950 dark:text-white">{knowledgeBase?.name || "Knowledge base"}</p>
            <p className="flex items-center gap-1 text-[11px] text-ink-500"><BookOpen size={11} /> Document-grounded chat</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {credits.data && <div className="hidden items-center gap-1.5 rounded-full bg-mist-50 px-3 py-1.5 text-xs font-medium text-ink-500 dark:bg-ink-800 sm:flex"><Coins size={13} className="text-stamp-teal" /><span className="text-ink-900 dark:text-white">{credits.data.balance}</span> credits</div>}
          <SignOutButton compact />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <SessionRail
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelect={setActiveSessionId}
          onCreateNew={handleCreateNew}
        />

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {(sessionsError || messagesError || createSession.error) && <p role="alert" className="m-3 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">{(sessionsError || messagesError || createSession.error)?.message}</p>}
        {messagesLoading && <div className="flex flex-1 items-center justify-center"><p className="text-sm text-ink-500">Loading conversation…</p></div>}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-6 scrollbar-thin sm:px-6 sm:py-8">
          <div className="mx-auto max-w-3xl space-y-7">
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
            <p className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
              {streamError}
            </p>
          )}

          {messages.length === 0 && !isStreaming && (
            <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-stamp-teal/10 text-stamp-teal"><Sparkles size={23} strokeWidth={1.7} /></div>
              <h1 className="mt-5 text-balance font-display text-2xl font-semibold tracking-[-0.02em] text-ink-950 dark:text-white">Ask your documents anything</h1>
              <p className="mt-2 max-w-md text-sm leading-6 text-ink-500">KnowledgeGPT will answer from this knowledge base and show the sources it used.</p>
              {activeSessionId ? (
                <div className="mt-6 flex max-w-xl flex-wrap justify-center gap-2">
                  {STARTER_QUESTIONS.map((question) => <button key={question} onClick={() => handleSend(question)} className="rounded-full border border-ink-950/10 bg-white px-3.5 py-2 text-xs font-medium text-ink-700 shadow-sm transition hover:border-stamp-teal/40 hover:text-stamp-teal dark:border-white/10 dark:bg-ink-900 dark:text-mist-100">{question}</button>)}
                </div>
              ) : (
                <button onClick={handleCreateNew} className="primary-button mt-6">Start a new chat</button>
              )}
            </div>
          )}
          </div>
        </div>

        <ChatInput onSend={handleSend} disabled={isStreaming || !activeSessionId} />
      </div>

      <SourcesRail citations={displayedCitations} activeIndex={activeCitationIndex} />
      </div>
    </div>
  );
}
