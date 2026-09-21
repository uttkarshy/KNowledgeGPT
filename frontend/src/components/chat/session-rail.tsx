"use client";

import { MessageCircle, MessageSquarePlus, Pin } from "lucide-react";
import type { ChatSession } from "@/types";

interface SessionRailProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onCreateNew: () => void;
}

export function SessionRail({ sessions, activeSessionId, onSelect, onCreateNew }: SessionRailProps) {
  return (
    <aside className="flex max-h-44 w-full shrink-0 flex-col border-b border-ink-950/[0.07] bg-mist-50/50 dark:border-white/10 dark:bg-ink-900/40 lg:max-h-none lg:w-60 lg:border-b-0 lg:border-r">
      <div className="flex items-center gap-2 p-3 lg:block lg:p-4">
        <button
          onClick={onCreateNew}
          className="secondary-button w-auto shrink-0 gap-2 px-3 py-2 text-xs lg:w-full lg:text-sm"
        >
          <MessageSquarePlus size={15} />
          New chat
        </button>
        <p className="mt-5 hidden px-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-300 lg:block">Conversations</p>
      </div>

      <div className="flex flex-1 gap-1 overflow-x-auto px-1 pb-3 scrollbar-thin lg:block lg:overflow-y-auto lg:overflow-x-hidden lg:px-3">
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => onSelect(session.id)}
            className={`flex w-auto max-w-52 shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-left text-xs transition lg:mb-1 lg:w-full lg:max-w-none lg:shrink lg:text-sm ${
              activeSessionId === session.id
                ? "bg-white text-ink-950 shadow-sm ring-1 ring-ink-950/[0.05] dark:bg-ink-800 dark:text-white dark:ring-white/10"
                : "text-ink-500 hover:bg-white/70 hover:text-ink-950 dark:text-mist-100 dark:hover:bg-ink-800"
            }`}
          >
            {session.is_pinned ? <Pin size={12} className="shrink-0 text-stamp-teal" /> : <MessageCircle size={12} className="shrink-0 text-ink-300" />}
            <span className="truncate">{session.title}</span>
          </button>
        ))}
        {sessions.length === 0 && (
          <p className="whitespace-nowrap px-3 py-2 text-xs text-ink-500">No conversations yet.</p>
        )}
      </div>
    </aside>
  );
}
