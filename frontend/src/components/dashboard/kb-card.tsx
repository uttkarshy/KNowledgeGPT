"use client";

import { Archive, ArrowUpRight, Copy, FileText, FolderOpen, MessageSquare, MoreHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";
import { formatBytes, formatRelativeTime } from "@/lib/format";
import type { KnowledgeBase } from "@/types";

interface KBCardProps {
  kb: KnowledgeBase;
  onOpen: () => void;
  onChat: () => void;
  onArchive: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

const DEFAULT_COLOR = "#146661"; // stamp-teal fallback

export function KBCard({ kb, onOpen, onChat, onArchive, onDuplicate, onDelete }: KBCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <article className="surface-card group relative flex min-h-52 flex-col overflow-visible p-5 transition duration-200 hover:-translate-y-0.5 hover:border-ink-950/10 hover:shadow-lg dark:hover:border-white/20">
      <div className="absolute inset-x-5 top-0 h-px" style={{ backgroundColor: kb.color || DEFAULT_COLOR }} aria-hidden="true" />
      <div className="flex items-start justify-between">
        <button onClick={onOpen} className="flex min-w-0 flex-1 items-start gap-3 text-left" aria-label={`Manage documents in ${kb.name}`}>
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ backgroundColor: `${kb.color || DEFAULT_COLOR}14`, color: kb.color || DEFAULT_COLOR }}>
            <FolderOpen size={19} strokeWidth={1.8} />
          </span>
          <span className="min-w-0 pt-0.5">
            <span className="block truncate font-display text-[17px] font-semibold text-ink-950 dark:text-white">{kb.name}</span>
            <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-[0.1em] text-ink-300">Updated {formatRelativeTime(kb.updated_at)}</span>
          </span>
        </button>

        <div className="relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-500 transition hover:bg-mist-100 hover:text-ink-900 dark:hover:bg-ink-800"
            aria-label="More options"
          >
            <MoreHorizontal size={17} />
          </button>
          {menuOpen && (
            <div
              className="absolute right-0 top-9 z-10 w-40 rounded-xl border border-ink-950/10 bg-white p-1.5 shadow-float dark:border-white/10 dark:bg-ink-900"
              onMouseLeave={() => setMenuOpen(false)}
            >
              <button
                onClick={() => {
                  onDuplicate();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-ink-700 hover:bg-mist-50 dark:text-mist-100 dark:hover:bg-ink-800"
              >
                <Copy size={13} /> Duplicate
              </button>
              <button
                onClick={() => {
                  onArchive();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-ink-700 hover:bg-mist-50 dark:text-mist-100 dark:hover:bg-ink-800"
              >
                <Archive size={13} /> Archive
              </button>
              <button
                onClick={() => {
                  onDelete();
                  setMenuOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-danger hover:bg-danger/10"
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {kb.description ? (
        <p className="mt-4 line-clamp-2 min-h-10 text-sm leading-5 text-ink-500">{kb.description}</p>
      ) : (
        <p className="mt-4 min-h-10 text-sm leading-5 text-ink-300">A workspace for related documents and grounded answers.</p>
      )}

      {kb.tags && kb.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {kb.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-mist-50 px-2 py-1 text-[10px] font-medium text-ink-500 dark:bg-ink-800"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto flex items-center gap-3 border-t border-ink-950/[0.06] pt-4 font-mono text-[10px] text-ink-500 dark:border-white/10">
        <span className="flex items-center gap-1">
          <FileText size={12} /> {kb.document_count} {kb.document_count === 1 ? "document" : "documents"}
        </span>
        <span>{formatBytes(kb.storage_bytes_used)}</span>
        <button onClick={onOpen} className="ml-auto flex items-center gap-1 font-body text-xs font-semibold text-stamp-teal hover:text-stamp-tealDark">Manage <ArrowUpRight size={13} /></button>
      </div>

      <button
        onClick={onChat}
        disabled={kb.document_count === 0}
        title={kb.document_count === 0 ? "Upload a document before starting a chat" : undefined}
        className="mt-3 flex items-center justify-center gap-1.5 rounded-xl bg-stamp-teal/[0.08] py-2 text-xs font-semibold text-stamp-teal transition hover:bg-stamp-teal/[0.14] disabled:cursor-not-allowed disabled:opacity-45"
      >
        <MessageSquare size={13} /> Ask this knowledge base
      </button>
    </article>
  );
}
