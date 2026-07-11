"use client";

import { Send } from "lucide-react";
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
    <div className="border-t border-mist-200 p-4 dark:border-ink-700">
      <div className="flex items-end gap-2 rounded-lg border border-mist-200 bg-white p-2 dark:border-ink-700 dark:bg-ink-900">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents…"
          rows={1}
          disabled={disabled}
          className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-ink-500"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Send question"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-stamp-teal text-white transition hover:bg-stamp-tealDark disabled:opacity-40"
        >
          <Send size={15} />
        </button>
      </div>
      <p className="mt-1.5 px-1 font-mono text-[10px] text-ink-500">
        KnowledgeGPT only answers from your uploaded documents and always cites its sources.
      </p>
    </div>
  );
}
