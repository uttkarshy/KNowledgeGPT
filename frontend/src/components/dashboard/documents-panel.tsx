"use client";

import { AlertCircle, ArrowRight, CheckCircle2, Clock3, FileText, Loader2, RotateCcw, Trash2, UploadCloud, X } from "lucide-react";
import { useRef, useState } from "react";
import { formatBytes } from "@/lib/format";
import { useDeleteDocument, useDocuments, useUploadDocument, useUploadLimits, useRetryProcessing } from "@/hooks/use-documents";
import type { DocumentSummary } from "@/types";
import { useCredits } from "@/hooks/use-billing";

interface DocumentsPanelProps {
  knowledgeBaseId: string;
  knowledgeBaseName?: string;
  onClose: () => void;
  onChat?: () => void;
}

const STATUS_LABELS: Record<DocumentSummary["status"], string> = {
  pending: "Waiting for upload",
  virus_scanning: "Scanning",
  extracting: "Extracting text",
  ocr_processing: "Running OCR",
  chunking: "Chunking",
  embedding: "Generating embeddings",
  completed: "Ready",
  failed: "Failed",
};

function StatusIcon({ status }: { status: DocumentSummary["status"] }) {
  if (status === "completed") return <CheckCircle2 size={15} className="text-success" />;
  if (status === "failed") return <AlertCircle size={15} className="text-danger" />;
  return <Loader2 size={15} className="animate-spin text-stamp-teal" />;
}

export function DocumentsPanel({ knowledgeBaseId, knowledgeBaseName, onClose, onChat }: DocumentsPanelProps) {
  const { data: documents = [], isLoading, error: loadError, refetch } = useDocuments(knowledgeBaseId);
  const limits = useUploadLimits();
  const retryProcessing = useRetryProcessing(knowledgeBaseId);
  const deleteDocument = useDeleteDocument(knowledgeBaseId);
  const { upload, confirmProcessing, pendingDocument, stage, progress, error } = useUploadDocument(knowledgeBaseId);
  const credits = useCredits();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload(file);
    e.target.value = "";
  };

  const isUploading = stage !== "idle" && stage !== "done" && stage !== "error";
  const estimate = pendingDocument?.estimated_credits ?? pendingDocument?.page_count ?? 1;
  const insufficientCredits = pendingDocument != null && credits.data != null && estimate > credits.data.balance;
  const readyCount = documents.filter((document) => document.status === "completed").length;

  const handleDrop = (event: React.DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file && !isUploading) upload(file);
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-950/35 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="documents-title">
      <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Close documents" />
      <div className="relative flex h-full w-full max-w-2xl flex-col border-l border-ink-950/10 bg-canvas shadow-float dark:border-white/10 dark:bg-ink-950">
        <div className="flex items-start justify-between border-b border-ink-950/[0.07] px-5 py-5 dark:border-white/10 sm:px-7">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-stamp-teal">Document workspace</p>
            <h2 id="documents-title" className="mt-1 truncate font-display text-2xl font-semibold tracking-[-0.02em] text-ink-950 dark:text-white">{knowledgeBaseName || "Documents"}</h2>
            <p className="mt-1 text-xs text-ink-500">{readyCount} ready · {documents.length} total</p>
          </div>
          <button aria-label="Close documents" onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-500 hover:bg-mist-50 dark:hover:bg-ink-800">
            <X size={18} />
          </button>
        </div>

        <div className="border-b border-ink-950/[0.07] p-5 dark:border-white/10 sm:p-7">
          <input ref={fileInputRef} type="file" accept={limits.data?.allowed_extensions.map(ext => `.${ext}`).join(",")} className="hidden" onChange={handleFileChange} />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || !limits.data}
            onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            className={`group flex w-full flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-7 text-center transition disabled:opacity-50 ${dragActive ? "border-stamp-teal bg-stamp-teal/[0.06]" : "border-ink-950/15 bg-white/70 hover:border-stamp-teal hover:bg-white dark:border-white/15 dark:bg-ink-900"}`}
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-stamp-teal/10 text-stamp-teal transition group-hover:scale-105"><UploadCloud size={21} strokeWidth={1.8} /></span>
            <span className="mt-3 text-sm font-semibold text-ink-900 dark:text-white">{isUploading ? `${stageLabel(stage)}${stage === "uploading" ? ` ${progress}%` : ""}` : "Drop a document here, or browse"}</span>
            <span className="mt-1 text-xs text-ink-500">Your file is checked before processing begins</span>
            {stage === "uploading" && <span className="mt-4 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-mist-100"><span className="block h-full rounded-full bg-stamp-teal transition-all" style={{ width: `${progress}%` }} /></span>}
          </button>
          <p className="mt-3 text-center text-xs leading-5 text-ink-500">{limits.data
            ? `${limits.data.allowed_extensions.map(ext => ext.toUpperCase()).join(", ")} · Up to ${formatBytes(limits.data.max_size_bytes)} · PDFs up to ${limits.data.max_pdf_pages} pages`
            : "Loading upload limits…"}</p>
          {limits.error && <p role="alert" className="text-xs text-danger">Upload limits unavailable. <button onClick={() => limits.refetch()}>Try again</button></p>}
          {stage === "done" && <p role="status" className="mt-3 rounded-xl border border-success/20 bg-success/10 px-3 py-2 text-xs text-ink-700">Upload received. Processing will continue below.</p>}
          {stage === "awaiting-confirmation" && pendingDocument && (
            <div className="mt-4 rounded-2xl border border-highlight-amber/25 bg-highlight-amber/[0.07] p-4">
              <div className="flex items-start justify-between gap-4">
                <div><p className="text-sm font-semibold text-ink-950 dark:text-white">Ready to process</p><p className="mt-1 text-xs leading-5 text-ink-500">{pendingDocument.page_count ?? 1} page(s) · approximately {estimate} credits</p></div>
                {credits.data && <span className="shrink-0 rounded-full bg-white px-2.5 py-1 font-mono text-[10px] text-ink-500 shadow-sm dark:bg-ink-900">Balance {credits.data.balance}</span>}
              </div>
              {insufficientCredits && <p role="alert" className="mt-3 rounded-lg bg-danger/10 px-3 py-2 text-xs leading-5 text-danger">You need {estimate - (credits.data?.balance ?? 0)} more credits to process this document. Buy credits from the dashboard, then return to continue.</p>}
              <button disabled={insufficientCredits} onClick={confirmProcessing} className="primary-button mt-4 gap-2 px-3 py-2 text-xs">Start processing <ArrowRight size={14} /></button>
            </div>
          )}
          {error && <p role="alert" className="mt-3 rounded-xl border border-danger/20 bg-danger/5 px-3 py-2 text-xs text-danger">{error}</p>}
        </div>

        <div className="flex-1 overflow-y-auto p-5 scrollbar-thin sm:p-7">
          <div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-semibold text-ink-950 dark:text-white">Uploaded files</h3>{documents.length > 0 && <span className="text-xs text-ink-500">{documents.length} total</span>}</div>
          {isLoading && <div className="space-y-3">{Array.from({ length: 3 }).map((_, index) => <div key={index} className="h-24 animate-pulse rounded-2xl bg-mist-50 dark:bg-ink-900" />)}</div>}
          {(loadError || deleteDocument.error || retryProcessing.error) && <p role="alert" className="rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">{(loadError || deleteDocument.error || retryProcessing.error)?.message} <button onClick={() => refetch()} className="font-semibold underline">Retry</button></p>}
          {!isLoading && !loadError && documents.length === 0 && (
            <div className="rounded-2xl border border-dashed border-ink-950/10 px-5 py-10 text-center dark:border-white/10"><FileText size={22} className="mx-auto text-ink-300" /><p className="mt-3 text-sm font-medium text-ink-700 dark:text-mist-100">No documents yet</p><p className="mt-1 text-xs text-ink-500">Upload a file above to begin building this knowledge base.</p></div>
          )}
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="surface-card p-4"
              >
                <div className="flex items-start gap-2">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-mist-50 text-ink-500 dark:bg-ink-800"><FileText size={16} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-ink-950 dark:text-white">{doc.name}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-500">
                      <StatusIcon status={doc.status} />
                      {STATUS_LABELS[doc.status]}
                      {doc.status !== "completed" && doc.status !== "failed" && (
                        <span>· {doc.processing_progress_pct}%</span>
                      )}
                      {(doc.page_count ?? 0) > 0 && doc.status !== "completed" && <span>· {doc.processed_page_count ?? 0}/{doc.page_count} pages</span>}
                      {doc.status === "completed" && (doc.page_count ?? 0) > 0 && <span>· {doc.page_count} pages</span>}
                      {doc.status === "completed" && <span>· {doc.chunk_count} sections</span>}
                    </div>
                    {doc.status_detail && (
                      <p className={`mt-1 text-[11px] ${doc.status === "failed" ? "text-danger" : "text-ink-500"}`}>{doc.status_detail}</p>
                    )}
                    {doc.status !== "completed" && doc.status !== "failed" && <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-mist-100 dark:bg-ink-800"><div className="h-full rounded-full bg-stamp-teal transition-all" style={{ width: `${doc.processing_progress_pct}%` }} /></div>}
                    {doc.next_retry_at && <p className="mt-2 flex items-center gap-1 text-xs text-ink-500"><Clock3 size={12} /> Automatic retry: {new Date(doc.next_retry_at).toLocaleTimeString()}</p>}
                    {doc.status === "failed" && doc.retryable && <button
                      disabled={retryProcessing.isPending}
                      onClick={() => retryProcessing.mutate(doc.id)}
                      className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-stamp-teal/10 px-2.5 py-1.5 text-xs font-semibold text-stamp-teal disabled:opacity-50"
><RotateCcw size={12} />{retryProcessing.isPending && retryProcessing.variables === doc.id ? "Queuing…" : "Retry Processing"}</button>}
                    <div className="mt-2 font-mono text-[10px] text-ink-300">
                      {formatBytes(doc.original_size_bytes)}
                    </div>
                  </div>
                  <button
                    disabled={deleteDocument.isPending}
                    onClick={() => { if (confirm(`Delete ${doc.name}?`)) deleteDocument.mutate(doc.id); }}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-300 hover:bg-danger/10 hover:text-danger"
                    aria-label={`Delete ${doc.name}`}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
        {onChat && readyCount > 0 && (
          <div className="border-t border-ink-950/[0.07] bg-white/80 p-4 backdrop-blur dark:border-white/10 dark:bg-ink-900/80 sm:px-7">
            <button onClick={onChat} className="primary-button w-full gap-2">Ask questions about {readyCount === 1 ? "this document" : "these documents"} <ArrowRight size={15} /></button>
          </div>
        )}
      </div>
    </div>
  );
}

function stageLabel(stage: string): string {
  switch (stage) {
    case "requesting-url":
      return "Preparing…";
    case "uploading":
      return "Uploading…";
    case "confirming":
      return "Confirming…";
    case "estimating":
      return "Checking pages and credits…";
    case "awaiting-confirmation":
      return "Ready to process";
    default:
      return "Working…";
  }
}
