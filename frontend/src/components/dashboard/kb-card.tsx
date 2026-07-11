"use client";

import { Copy, FileText, MessageSquare, MoreVertical, Trash2 } from "lucide-react";
import { useState } from "react";
import { formatBytes, formatRelativeTime } from "@/lib/format";
import type { KnowledgeBase } from "@/types";

interface KBCardProps {
  kb: KnowledgeBase;
  onOpen: () => void;
  onArchive: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

const DEFAULT_COLOR = "#146661"; // stamp-teal fallback

export function KBCard({ kb, onOpen, onArchive, onDuplicate, onDelete }: KBCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div
      className="group relative flex flex-col rounded-md border border-mist-200 bg-white p-4 shadow-sm transition hover:shadow-md dark:border-ink-700 dark:bg-ink-900"
      style={{ borderTopWidth: 3, borderTopColor: kb.color || DEFAULT_COLOR }}
    >
      <div className="flex items-start justify-between">
        <button onClick={onOpen} className="min-w-0 flex-1 text-left">
          <h3 className="truncate font-display text-base font-medium text-ink-900 dark:text-mist-50">
            {kb.name}
          </h3>
          {kb.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-ink-500">{kb.description}</p>
          )}
        </button>

        <div className="relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="rounded p-1 text-ink-500 opacity-0 transition hover:bg-mist-100 group-hover:opacity-100 dark:hover:bg-ink-800"
            aria-label="More options"
          >
            <MoreVertical size={16} />
          </button>
          {menuOpen && (
            <div
              className="absolute right-0 top-7 z-10 w-36 rounded-md border border-mist-200 bg-white py-1 shadow-lg dark:border-ink-700 dark:bg-ink-900"
              onMouseLeave={() => setMenuOpen(false)}
            >
              <button
                onClick={() => {
                  onDuplicate();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-ink-700 hover:bg-mist-100 dark:text-mist-100 dark:hover:bg-ink-800"
              >
                <Copy size={13} /> Duplicate
              </button>
              <button
                onClick={() => {
                  onArchive();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-ink-700 hover:bg-mist-100 dark:text-mist-100 dark:hover:bg-ink-800"
              >
                Archive
              </button>
              <button
                onClick={() => {
                  onDelete();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-danger hover:bg-danger/10"
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {kb.tags && kb.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {kb.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded bg-mist-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-500 dark:bg-ink-800"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-center gap-3 font-mono text-[11px] text-ink-500">
        <span className="flex items-center gap-1">
          <FileText size={12} /> {kb.document_count}
        </span>
        <span>{formatBytes(kb.storage_bytes_used)}</span>
        <span className="ml-auto">{formatRelativeTime(kb.updated_at)}</span>
      </div>

      <button
        onClick={onOpen}
        className="mt-3 flex items-center justify-center gap-1.5 rounded-md border border-mist-200 py-1.5 text-xs text-ink-700 transition hover:border-stamp-teal hover:text-stamp-teal dark:border-ink-700 dark:text-mist-100"
      >
        <MessageSquare size={13} /> Open chat
      </button>
    </div>
  );
}
