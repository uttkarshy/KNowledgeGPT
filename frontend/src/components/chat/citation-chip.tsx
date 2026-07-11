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
        mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-tab
        border border-highlight-amberDark/30 bg-highlight-amber/90 px-1.5
        font-mono text-[11px] font-medium leading-none text-white
        transition hover:bg-highlight-amberDark
        ${isActive ? "ring-2 ring-highlight-amberDark ring-offset-1" : ""}
      `}
    >
      {index}
    </button>
  );
}
