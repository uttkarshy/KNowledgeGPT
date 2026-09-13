"use client";

import { FileText } from "lucide-react";
import type { Citation } from "@/types";

interface SourcesRailProps {
  citations: Citation[];
  activeIndex: number | null;
}

/** Renders each citation as a stacked "index card" — the confidence score
 * shows as a dotted-fill meter rather than a percentage badge, continuing
 * the ledger/archive visual language instead of a generic progress bar. */
export function SourcesRail({ citations, activeIndex }: SourcesRailProps) {
  if (citations.length === 0) {
    return (
      <aside className="w-full max-h-40 lg:max-h-none lg:w-72 shrink-0 border-l border-mist-200 p-4 dark:border-ink-700">
        <h2 className="font-mono text-xs uppercase tracking-wide text-ink-500">Sources</h2>
        <p className="mt-3 text-sm text-ink-500">
          Sources for the current answer will appear here.
        </p>
      </aside>
    );
  }

  return (
    <aside className="w-full max-h-52 lg:max-h-none lg:w-80 shrink-0 overflow-y-auto border-l border-mist-200 p-4 dark:border-ink-700 scrollbar-thin">
      <h2 className="font-mono text-xs uppercase tracking-wide text-ink-500">
        Sources ({citations.length})
      </h2>
      <div className="mt-3 space-y-3">
        {citations.map((citation, i) => {
          const index = i + 1;
          const isActive = activeIndex === index;
          const filledDots = Math.round(citation.similarity_score * 10);

          return (
            <div
              key={`${citation.document_id}-${citation.page_number}-${i}`}
              id={`source-card-${index}`}
              className={`rounded-md border bg-white p-3 dark:bg-ink-900 ${
                isActive
                  ? "border-highlight-amber animate-pulse-glow"
                  : "border-mist-200 dark:border-ink-700"
              }`}
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-tab bg-highlight-amber font-mono text-[11px] font-medium text-white">
                  {index}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 text-sm font-medium text-ink-900 dark:text-mist-50">
                    <FileText size={14} className="shrink-0 text-ink-500" />
                    <span className="truncate">{citation.document_name}</span>
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-ink-500">
                    {citation.section && <span>{citation.section} · </span>}
                    {citation.page_number && <span>p. {citation.page_number}</span>}
                  </div>
                </div>
              </div>

              <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-ink-700 dark:text-mist-100">
                {citation.excerpt}
              </p>

              <div className="mt-2 flex items-center gap-1.5">
                <span className="font-mono text-[10px] text-ink-500">match</span>
                <div className="flex gap-0.5">
                  {Array.from({ length: 10 }).map((_, dotIndex) => (
                    <span
                      key={dotIndex}
                      className={`h-1.5 w-1.5 rounded-full ${
                        dotIndex < filledDots ? "bg-stamp-teal" : "bg-mist-200 dark:bg-ink-700"
                      }`}
                    />
                  ))}
                </div>
                <span className="font-mono text-[10px] text-ink-500">
                  {Math.round(citation.similarity_score * 100)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
