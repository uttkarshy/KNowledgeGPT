"use client";

import { Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CreateKBDialog } from "@/components/dashboard/create-kb-dialog";
import { CreditsCard } from "@/components/dashboard/credits-card";
import { DocumentsPanel } from "@/components/dashboard/documents-panel";
import { KBCard } from "@/components/dashboard/kb-card";
import { StatsOverview } from "@/components/dashboard/stats-overview";
import {
  useArchiveKnowledgeBase,
  useDeleteKnowledgeBase,
  useDuplicateKnowledgeBase,
  useKnowledgeBases,
} from "@/hooks/use-knowledge-bases";

export default function DashboardPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [openDocsForKB, setOpenDocsForKB] = useState<string | null>(null);

  const { data: knowledgeBases = [], isLoading, error, refetch } = useKnowledgeBases(search);
  const archiveKB = useArchiveKnowledgeBase();
  const duplicateKB = useDuplicateKnowledgeBase();
  const deleteKB = useDeleteKnowledgeBase();

  return (
    <main className="min-h-screen bg-mist-50 p-6 pt-14 dark:bg-ink-950">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-2xl text-ink-900 dark:text-mist-50">Knowledge bases</h1>
          <button
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-1.5 rounded-md bg-stamp-teal px-3.5 py-2 text-sm font-medium text-white hover:bg-stamp-tealDark"
          >
            <Plus size={15} /> New knowledge base
          </button>
        </div>

        {isLoading && <p className="mt-4">Loading knowledge bases…</p>}
        {(error || archiveKB.error || duplicateKB.error || deleteKB.error) && <div role="alert" className="mt-4 text-sm text-danger">{(error || archiveKB.error || duplicateKB.error || deleteKB.error)?.message} <button onClick={() => refetch()} className="underline">Retry</button></div>}
        <div className="mt-5">
          <StatsOverview knowledgeBases={knowledgeBases} />
        </div>
        <CreditsCard />

        <div className="mt-6 flex items-center gap-2 rounded-md border border-mist-200 bg-white px-3 py-2 dark:border-ink-700 dark:bg-ink-900">
          <Search size={15} className="text-ink-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search knowledge bases…"
            className="flex-1 bg-transparent text-sm outline-none"
          />
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {knowledgeBases.map((kb) => (
            <KBCard
              key={kb.id}
              kb={kb}
              onOpen={() => setOpenDocsForKB(kb.id)}
              onArchive={() => archiveKB.mutate(kb.id)}
              onDuplicate={() => duplicateKB.mutate(kb.id)}
              onDelete={() => {
                if (confirm(`Delete "${kb.name}" and all its documents? This cannot be undone.`)) {
                  deleteKB.mutate(kb.id);
                }
              }}
            />
          ))}
        </div>

        {!isLoading && !error && knowledgeBases.length === 0 && (
          <div className="mt-16 text-center">
            <p className="text-sm text-ink-500">
              No knowledge bases yet. Create one to start uploading documents.
            </p>
          </div>
        )}
      </div>

      {createOpen && <CreateKBDialog open={createOpen} onClose={() => setCreateOpen(false)} />}

      {openDocsForKB && (
        <DocumentsPanel knowledgeBaseId={openDocsForKB} onClose={() => setOpenDocsForKB(null)} />
      )}

      {openDocsForKB && (
        <div className="fixed bottom-6 right-6 z-50">
          <button
            onClick={() => router.push(`/chat?kb=${openDocsForKB}`)}
            className="rounded-full bg-stamp-teal px-4 py-2 text-sm font-medium text-white shadow-lg hover:bg-stamp-tealDark"
          >
            Chat with this knowledge base →
          </button>
        </div>
      )}
    </main>
  );
}
