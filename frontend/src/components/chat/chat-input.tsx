"use client";

import { CornerDownLeft, Send } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (question: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="shrink-0 border-t border-ink-950/[0.07] bg-canvas/90 px-3 py-3 backdrop-blur-xl dark:border-white/10 dark:bg-ink-950/90 sm:px-6 sm:py-4">
      <div className="mx-auto max-w-3xl">
      <div className="flex items-end gap-2 rounded-2xl border border-ink-950/10 bg-white p-2 shadow-card transition focus-within:border-stamp-teal/40 focus-within:shadow-lg dark:border-white/10 dark:bg-ink-900">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents…"
          rows={1}
          maxLength={600}
          aria-label="Question about your documents"
          disabled={disabled}
          className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2.5 py-2 text-sm leading-6 text-ink-900 outline-none placeholder:text-ink-300 dark:text-white"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Send question"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-stamp-teal text-white shadow-sm transition hover:bg-stamp-tealDark disabled:opacity-35"
        >
          <Send size={15} />
        </button>
      </div>
      <div className="mt-2 flex items-center justify-between gap-3 px-1 text-[10px] text-ink-500"><p>Answers use your documents. Verify important details in the cited sources.</p><span className="hidden shrink-0 items-center gap-1 font-mono sm:flex"><CornerDownLeft size={10} /> Enter to send</span></div>
      </div>
    </div>
  );
}
