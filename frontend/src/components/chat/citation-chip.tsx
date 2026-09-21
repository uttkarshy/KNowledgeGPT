"use client";

interface CitationChipProps {
  index: number;
  onClick: () => void;
  isActive?: boolean;
}

/**
 * Renders as a small file-tab shape (rounded top corners only, like a
 * library catalog card tab) in highlight-amber. This is the one place in
 * the UI that color appears — reserved deliberately so it always signals
 * "this claim traces to a source."
 */
export function CitationChip({ index, onClick, isActive }: CitationChipProps) {
  return (
    <button
      onClick={onClick}
      aria-label={`View source ${index}`}
      className={`
        mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-md
        border border-highlight-amber/25 bg-highlight-amber/10 px-1.5
        font-mono text-[10px] font-semibold leading-none text-highlight-amberDark
        transition hover:border-highlight-amber/50 hover:bg-highlight-amber/20
        ${isActive ? "ring-2 ring-highlight-amber/40 ring-offset-1" : ""}
      `}
    >
      {index}
    </button>
  );
}
