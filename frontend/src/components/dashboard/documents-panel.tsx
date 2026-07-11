"use client";

import { AlertCircle, CheckCircle2, FileText, Loader2, Trash2, Upload, X } from "lucide-react";
import { useRef } from "react";
import { formatBytes } from "@/lib/format";
import { useDeleteDocument, useDocuments, useUploadDocument } from "@/hooks/use-documents";
import type { DocumentSummary } from "@/types";

interface DocumentsPanelProps {
  knowledgeBaseId: string;
  onClose: () => void;
}

const STATUS_LABELS: Record<DocumentSummary["status"], string> = {
  pending: "Queued",
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

export function DocumentsPanel({ knowledgeBaseId, onClose }: DocumentsPanelProps) {
  const { data: documents = [] } = useDocuments(knowledgeBaseId);
  const deleteDocument = useDeleteDocument(knowledgeBaseId);
  const { upload, stage, progress, error } = useUploadDocument(knowledgeBaseId);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload(file);
    e.target.value = "";
  };

  const isUploading = stage !== "idle" && stage !== "done" && stage !== "error";

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-950/30">
      <div className="flex h-full w-full max-w-md flex-col border-l border-mist-200 bg-white dark:border-ink-700 dark:bg-ink-900">
        <div className="flex items-center justify-between border-b border-mist-200 p-4 dark:border-ink-700">
          <h2 className="font-display text-base text-ink-900 dark:text-mist-50">Documents</h2>
          <button onClick={onClose} className="rounded p-1 hover:bg-mist-100 dark:hover:bg-ink-800">
            <X size={18} />
          </button>
        </div>

        <div className="border-b border-mist-200 p-4 dark:border-ink-700">
          <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileChange} />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-dashed border-mist-200 py-3 text-sm text-ink-700 transition hover:border-stamp-teal hover:text-stamp-teal disabled:opacity-50 dark:border-ink-700 dark:text-mist-100"
          >
            <Upload size={15} />
            {isUploading ? `${stageLabel(stage)}${stage === "uploading" ? ` ${progress}%` : ""}` : "Upload a document"}
          </button>
          {error && <p className="mt-2 text-xs text-danger">{error}</p>}
        </div>

        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
          {documents.length === 0 && (
            <p className="text-sm text-ink-500">No documents yet. Upload one to get started.</p>
          )}
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="rounded-md border border-mist-200 p-3 dark:border-ink-700"
              >
                <div className="flex items-start gap-2">
                  <FileText size={15} className="mt-0.5 shrink-0 text-ink-500" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-ink-900 dark:text-mist-50">{doc.name}</div>
                    <div className="mt-0.5 flex items-center gap-1.5 font-mono text-[11px] text-ink-500">
                      <StatusIcon status={doc.status} />
                      {STATUS_LABELS[doc.status]}
                      {doc.status !== "completed" && doc.status !== "failed" && (
                        <span>· {doc.processing_progress_pct}%</span>
                      )}
                      {doc.status === "completed" && <span>· {doc.chunk_count} chunks</span>}
                    </div>
                    {doc.status === "failed" && doc.status_detail && (
                      <p className="mt-1 text-[11px] text-danger">{doc.status_detail}</p>
                    )}
                    <div className="mt-1 font-mono text-[10px] text-ink-500">
                      {formatBytes(doc.original_size_bytes)}
                    </div>
                  </div>
                  <button
                    onClick={() => deleteDocument.mutate(doc.id)}
                    className="shrink-0 rounded p-1 text-ink-500 hover:bg-danger/10 hover:text-danger"
                    aria-label={`Delete ${doc.name}`}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
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
    default:
      return "Working…";
  }
}
