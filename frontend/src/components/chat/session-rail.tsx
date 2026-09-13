"use client";

import { MessageSquarePlus, Pin } from "lucide-react";
import type { ChatSession } from "@/types";

interface SessionRailProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onCreateNew: () => void;
}

export function SessionRail({ sessions, activeSessionId, onSelect, onCreateNew }: SessionRailProps) {
  return (
    <aside className="flex max-h-40 w-full shrink-0 flex-col lg:max-h-none lg:w-64 border-r border-mist-200 dark:border-ink-700">
      <div className="p-3">
        <button
          onClick={onCreateNew}
          className="flex w-full items-center gap-2 rounded-md border border-mist-200 px-3 py-2 text-sm text-ink-700 transition hover:border-stamp-teal hover:text-stamp-teal dark:border-ink-700 dark:text-mist-100"
        >
          <MessageSquarePlus size={15} />
          New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3 scrollbar-thin">
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => onSelect(session.id)}
            className={`mb-0.5 flex w-full items-center gap-1.5 rounded-md px-3 py-2 text-left text-sm transition ${
              activeSessionId === session.id
                ? "bg-stamp-teal/10 text-stamp-teal"
                : "text-ink-700 hover:bg-mist-100 dark:text-mist-100 dark:hover:bg-ink-800"
            }`}
          >
            {session.is_pinned && <Pin size={12} className="shrink-0" />}
            <span className="truncate">{session.title}</span>
          </button>
        ))}
        {sessions.length === 0 && (
          <p className="px-3 py-2 text-xs text-ink-500">No conversations yet.</p>
        )}
      </div>
    </aside>
  );
}
