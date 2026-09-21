"use client";

import { Sparkles, User } from "lucide-react";
import { MessageContent } from "@/components/chat/message-content";
import type { Citation } from "@/types";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  modelUsed?: string | null;
  latencyMs?: number | null;
  inputTokens?: number | null;
  outputTokens?: number | null;
  activeCitationIndex: number | null;
  onCitationClick: (index: number) => void;
}

export function MessageBubble({
  role,
  content,
  citations = [],
  modelUsed,
  latencyMs,
  inputTokens,
  outputTokens,
  activeCitationIndex,
  onCitationClick,
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3.5 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${
          isUser ? "bg-ink-900 text-white" : "bg-stamp-teal/10 text-stamp-teal"
        }`}
      >
        {isUser ? <User size={14} /> : <Sparkles size={14} />}
      </div>

      <div className={`flex min-w-0 flex-col ${isUser ? "max-w-[85%] items-end sm:max-w-[72%]" : "max-w-[calc(100%-2.875rem)] flex-1 items-start"}`}>
        <div
          className={`text-sm ${
            isUser
              ? "rounded-2xl rounded-tr-md bg-ink-900 px-4 py-2.5 leading-6 text-white shadow-sm"
              : "w-full pt-0.5 text-ink-700 dark:text-mist-100"
          }`}
        >
          {isUser ? (
            <span>{content}</span>
          ) : (
            <MessageContent
              content={content}
              citations={citations}
              activeCitationIndex={activeCitationIndex}
              onCitationClick={onCitationClick}
            />
          )}
        </div>

        {!isUser && (modelUsed || latencyMs) && (
          <div className="mt-2 flex gap-2 font-mono text-[9px] uppercase tracking-wide text-ink-300">
            {modelUsed && <span>{modelUsed}</span>}
            {latencyMs != null && <span>{(latencyMs / 1000).toFixed(1)}s</span>}
            {inputTokens != null && outputTokens != null && (
              <span>
                {inputTokens + outputTokens} tokens
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
