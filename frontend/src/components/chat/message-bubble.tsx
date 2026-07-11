"use client";

import { Bot, User } from "lucide-react";
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
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-ink-700 text-mist-50" : "bg-stamp-teal text-white"
        }`}
      >
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        <div
          className={`rounded-lg px-4 py-2.5 text-sm ${
            isUser
              ? "bg-ink-700 text-mist-50"
              : "border border-mist-200 bg-white text-ink-700 dark:border-ink-700 dark:bg-ink-900 dark:text-mist-100"
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
          <div className="mt-1 flex gap-2 font-mono text-[10px] text-ink-500">
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
