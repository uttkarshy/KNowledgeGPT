"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { rehypeCitations } from "./rehype-citations";
import { CitationChip } from "@/components/chat/citation-chip";
import type { Citation } from "@/types";

interface MessageContentProps {
  content: string;
  citations: Citation[];
  activeCitationIndex: number | null;
  onCitationClick: (index: number) => void;
}

/** Parse the whole answer before inserting interactive citation markers. */
export function MessageContent({ content, citations, activeCitationIndex, onCitationClick }: MessageContentProps) {
  return (
    <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-headings:font-display">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight, [rehypeCitations, { count: citations.length }]]}
        components={{
          span: ({ node, children, ...props }) => {
            const index = Number(node?.properties["data-citation"]);
            return Number.isInteger(index) && index >= 1 && index <= citations.length ? (
              <CitationChip index={index} isActive={activeCitationIndex === index} onClick={() => onCitationClick(index)} />
            ) : <span {...props}>{children}</span>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
