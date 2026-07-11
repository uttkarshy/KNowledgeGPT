"use client";

import { Database, FileStack, HardDrive } from "lucide-react";
import { formatBytes } from "@/lib/format";
import type { KnowledgeBase } from "@/types";

export function StatsOverview({ knowledgeBases }: { knowledgeBases: KnowledgeBase[] }) {
  const totalDocuments = knowledgeBases.reduce((sum, kb) => sum + kb.document_count, 0);
  const totalStorage = knowledgeBases.reduce((sum, kb) => sum + kb.storage_bytes_used, 0);

  const stats = [
    { label: "Knowledge bases", value: knowledgeBases.length, icon: Database },
    { label: "Documents", value: totalDocuments, icon: FileStack },
    { label: "Storage in use", value: formatBytes(totalStorage), icon: HardDrive },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {stats.map(({ label, value, icon: Icon }) => (
        <div
          key={label}
          className="flex items-center gap-3 rounded-md border border-mist-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-stamp-teal/10 text-stamp-teal">
            <Icon size={17} />
          </div>
          <div>
            <div className="font-display text-xl text-ink-900 dark:text-mist-50">{value}</div>
            <div className="font-mono text-[11px] text-ink-500">{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
