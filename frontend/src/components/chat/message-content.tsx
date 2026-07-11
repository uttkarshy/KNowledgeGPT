"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { CitationChip } from "@/components/chat/citation-chip";
import type { Citation } from "@/types";

interface MessageContentProps {
  content: string;
  citations: Citation[];
  activeCitationIndex: number | null;
  onCitationClick: (index: number) => void;
}

const CITATION_MARKER_RE = /\[(\d+)\]/g;

/**
 * Splits the message text on [N] citation markers and interleaves
 * markdown-rendered text segments with CitationChip buttons.
 *
 * Known limitation: this splits at the whole-message level before markdown
 * parsing, so a citation marker that falls INSIDE a bold/italic run or a
 * table cell (rare in practice — models place citations at claim/sentence
 * boundaries) may render awkwardly. Good enough for v1; a proper fix would
 * be a custom remark plugin operating on the parsed AST instead of raw text.
 */
export function MessageContent({ content, citations, activeCitationIndex, onCitationClick }: MessageContentProps) {
  const parts = content.split(CITATION_MARKER_RE);

  return (
    <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-headings:font-display">
      {parts.map((part, i) => {
        // Odd indices are the captured citation numbers (from String.split
        // with a capturing group regex); even indices are plain text.
        if (i % 2 === 1) {
          const index = parseInt(part, 10);
          if (citations.length > 0 && index >= 1 && index <= citations.length) {
            return (
              <CitationChip
                key={i}
                index={index}
                isActive={activeCitationIndex === index}
                onClick={() => onCitationClick(index)}
              />
            );
          }
          return <span key={i}>[{part}]</span>;
        }
        if (!part) return null;
        return (
          <ReactMarkdown
            key={i}
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{ p: ({ children }) => <span>{children} </span> }}
          >
            {part}
          </ReactMarkdown>
        );
      })}
    </div>
  );
}
