"use client";

import { BookOpen, FileStack, Plus, Search, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CreateKBDialog } from "@/components/dashboard/create-kb-dialog";
import { CreditsCard } from "@/components/dashboard/credits-card";
import { DocumentsPanel } from "@/components/dashboard/documents-panel";
import { KBCard } from "@/components/dashboard/kb-card";
import { AppShell } from "@/components/app-shell";
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
    <AppShell>
      <main className="min-h-dvh px-4 py-7 sm:px-7 sm:py-10 xl:px-12">
      <div className="mx-auto max-w-[90rem]">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-stamp-teal">
              <Sparkles size={13} /> Your workspace
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-ink-950 dark:text-white sm:text-4xl">Knowledge bases</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-ink-500 sm:text-base">Your documents, organized and ready to answer.</p>
          </div>
          <button
            onClick={() => setCreateOpen(true)}
            className="primary-button w-full gap-2 sm:w-auto"
          >
            <Plus size={16} /> New knowledge base
          </button>
        </div>

        <div className="mt-9 grid gap-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <section className="min-w-0">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative w-full sm:max-w-sm">
                <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-300" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search your knowledge bases"
                  aria-label="Search knowledge bases"
                  className="field-control pl-10"
                />
              </div>
              {!isLoading && knowledgeBases.length > 0 && (
                <p className="text-xs text-ink-500">
                  {knowledgeBases.length} {knowledgeBases.length === 1 ? "knowledge base" : "knowledge bases"}
                </p>
              )}
            </div>

            {(error || archiveKB.error || duplicateKB.error || deleteKB.error) && (
              <div role="alert" className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-danger/20 bg-danger/5 px-4 py-3 text-sm text-danger">
                <span>{(error || archiveKB.error || duplicateKB.error || deleteKB.error)?.message}</span>
                <button onClick={() => refetch()} className="shrink-0 font-semibold underline underline-offset-2">Retry</button>
              </div>
            )}

            {isLoading ? (
              <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3" aria-label="Loading knowledge bases">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="surface-card h-52 animate-pulse bg-white/60" />
                ))}
              </div>
            ) : (
              <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {knowledgeBases.map((kb) => (
                  <KBCard
                    key={kb.id}
                    kb={kb}
                    onOpen={() => setOpenDocsForKB(kb.id)}
                    onChat={() => router.push(`/chat?kb=${kb.id}`)}
                    onArchive={() => archiveKB.mutate(kb.id)}
                    onDuplicate={() => duplicateKB.mutate(kb.id)}
                    onDelete={() => {
                      if (confirm(`Delete "${kb.name}" and all its documents? This cannot be undone.`)) deleteKB.mutate(kb.id);
                    }}
                  />
                ))}
              </div>
            )}

            {!isLoading && !error && knowledgeBases.length === 0 && (
              <div className="surface-card mt-5 flex min-h-80 flex-col items-center justify-center px-6 py-12 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-stamp-teal/10 text-stamp-teal"><BookOpen size={24} strokeWidth={1.7} /></div>
                <h2 className="mt-5 font-display text-xl font-semibold text-ink-950 dark:text-white">Create your first knowledge base</h2>
                <p className="mt-2 max-w-sm text-sm leading-6 text-ink-500">Group related documents together, then ask questions and verify the answers with citations.</p>
                <button onClick={() => setCreateOpen(true)} className="primary-button mt-6 gap-2"><Plus size={16} /> New knowledge base</button>
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <CreditsCard />
            <div className="surface-card p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink-950 dark:text-white"><FileStack size={16} className="text-stamp-teal" /> How it works</div>
              <ol className="mt-4 space-y-4">
                {["Create a knowledge base", "Upload and process documents", "Ask questions and inspect citations"].map((step, index) => (
                  <li key={step} className="flex gap-3 text-sm leading-5 text-ink-500">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-mist-100 font-mono text-[10px] font-semibold text-ink-700 dark:bg-ink-800">{index + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          </aside>
        </div>
      </div>

      {createOpen && <CreateKBDialog open={createOpen} onClose={() => setCreateOpen(false)} />}

      {openDocsForKB && (
        <DocumentsPanel
          knowledgeBaseId={openDocsForKB}
          knowledgeBaseName={knowledgeBases.find((kb) => kb.id === openDocsForKB)?.name}
          onClose={() => setOpenDocsForKB(null)}
          onChat={() => router.push(`/chat?kb=${openDocsForKB}`)}
        />
      )}
      </main>
    </AppShell>
  );
}
