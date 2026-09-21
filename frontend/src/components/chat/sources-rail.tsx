"use client";

import { FileText, Quote, ShieldCheck } from "lucide-react";
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
      <aside className="hidden w-72 shrink-0 border-l border-ink-950/[0.07] bg-white/40 p-5 dark:border-white/10 dark:bg-ink-900/30 xl:block">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink-950 dark:text-white"><ShieldCheck size={16} className="text-stamp-teal" /> Sources</div>
        <div className="mt-5 rounded-2xl border border-dashed border-ink-950/10 p-5 text-center dark:border-white/10"><Quote size={19} className="mx-auto text-ink-300" /><p className="mt-3 text-xs leading-5 text-ink-500">Evidence for the current answer will appear here.</p></div>
      </aside>
    );
  }

  return (
    <aside className="max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-ink-950/[0.07] bg-white/70 p-4 backdrop-blur dark:border-white/10 dark:bg-ink-900/60 lg:max-h-none lg:w-80 lg:border-l lg:border-t-0 xl:w-96 xl:p-5 scrollbar-thin">
      <div className="flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold text-ink-950 dark:text-white"><ShieldCheck size={16} className="text-stamp-teal" /> Evidence</h2><span className="rounded-full bg-highlight-amber/10 px-2 py-1 font-mono text-[10px] font-semibold text-highlight-amberDark">{citations.length} {citations.length === 1 ? "source" : "sources"}</span></div>
      <p className="mt-1 text-xs leading-5 text-ink-500">Inspect the excerpts used for this answer.</p>
      <div className="mt-4 space-y-3">
        {citations.map((citation, i) => {
          const index = i + 1;
          const isActive = activeIndex === index;
          const filledDots = Math.round(citation.similarity_score * 10);

          return (
            <div
              key={`${citation.document_id}-${citation.page_number}-${i}`}
              id={`source-card-${index}`}
              className={`relative overflow-hidden rounded-2xl border bg-white p-4 shadow-sm transition dark:bg-ink-900 ${
                isActive
                  ? "border-highlight-amber/70 ring-4 ring-highlight-amber/10 animate-pulse-glow"
                  : "border-ink-950/[0.08] hover:border-highlight-amber/35 dark:border-white/10"
              }`}
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-highlight-amber/10 font-mono text-[10px] font-semibold text-highlight-amberDark">
                  {index}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 text-sm font-semibold text-ink-950 dark:text-white">
                    <FileText size={14} className="shrink-0 text-ink-500" />
                    <span className="truncate">{citation.document_name}</span>
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-ink-500">
                    {citation.section && <span>{citation.section} · </span>}
                    {citation.page_number && <span>p. {citation.page_number}</span>}
                  </div>
                </div>
              </div>

              <div className="mt-3 border-l-2 border-highlight-amber/30 pl-3"><p className={`${isActive ? "line-clamp-none" : "line-clamp-5"} text-xs leading-5 text-ink-700 dark:text-mist-100`}>
                {citation.excerpt}
              </p></div>

              <div className="mt-2 flex items-center gap-1.5">
                <span className="font-mono text-[9px] uppercase tracking-wide text-ink-300">relevance</span>
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
