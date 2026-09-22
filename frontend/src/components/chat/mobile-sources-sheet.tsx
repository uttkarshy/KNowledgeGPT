"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import { SourcesRail } from "@/components/chat/sources-rail";
import type { Citation } from "@/types";

interface MobileSourcesSheetProps {
  open: boolean;
  citations: Citation[];
  activeIndex: number | null;
  onClose: () => void;
}

export function MobileSourcesSheet({ open, citations, activeIndex, onClose }: MobileSourcesSheetProps) {
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open || citations.length === 0) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Evidence">
      <button
        type="button"
        className="absolute inset-0 bg-ink-950/40 backdrop-blur-[1px]"
        aria-label="Close evidence"
        onClick={onClose}
      />
      <section className="absolute inset-x-0 bottom-0 max-h-[78dvh] overflow-hidden rounded-t-3xl border-t border-ink-950/[0.08] bg-white shadow-2xl dark:border-white/10 dark:bg-ink-900">
        <div className="flex items-center justify-between border-b border-ink-950/[0.07] px-4 py-3 dark:border-white/10">
          <div className="mx-auto h-1 w-10 rounded-full bg-ink-950/15 dark:bg-white/20" aria-hidden="true" />
          <button
            type="button"
            onClick={onClose}
            className="absolute right-3 top-2.5 flex h-8 w-8 items-center justify-center rounded-full text-ink-500 transition hover:bg-mist-50 hover:text-ink-950 dark:hover:bg-ink-800 dark:hover:text-white"
            aria-label="Close evidence"
          >
            <X size={17} />
          </button>
        </div>
        <div className="max-h-[calc(78dvh-3.25rem)] overflow-y-auto overscroll-contain scrollbar-thin">
          <SourcesRail citations={citations} activeIndex={activeIndex} idPrefix="mobile-source-card" />
        </div>
      </section>
    </div>
  );
}
