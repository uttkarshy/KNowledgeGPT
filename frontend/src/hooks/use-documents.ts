"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch, apiJson } from "@/lib/api-client";
import type { DocumentSummary } from "@/types";

export function useDocuments(knowledgeBaseId: string | null) {
  return useQuery({
    queryKey: ["documents", knowledgeBaseId],
    queryFn: () => apiJson<DocumentSummary[]>(`/api/documents?knowledge_base_id=${knowledgeBaseId}`),
    enabled: !!knowledgeBaseId,
    // Poll while any document is still processing, so the UI reflects
    // status transitions (pending -> virus_scanning -> ... -> completed)
    // without the user needing to refresh.
    refetchInterval: (query) => {
      const docs = query.state.data as DocumentSummary[] | undefined;
      const stillProcessing = docs?.some((d) => d.status !== "completed" && d.status !== "failed");
      return stillProcessing ? 2000 : false;
    },
  });
}

export function useDeleteDocument(knowledgeBaseId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson<void>(`/api/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", knowledgeBaseId] }),
  });
}

export type UploadStage = "idle" | "requesting-url" | "uploading" | "confirming" | "done" | "error";

/**
 * Drives the full 3-step upload flow built in the Upload Service increment:
 *   1. POST /api/documents/upload-url  -> presigned S3 PUT URL
 *   2. PUT the file bytes directly to S3 (bypasses our API entirely)
 *   3. POST /api/documents/confirm     -> verifies + enqueues processing
 */
export function useUploadDocument(knowledgeBaseId: string | null) {
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<UploadStage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const upload = async (file: File) => {
    if (!knowledgeBaseId) return;
    setError(null);
    setProgress(0);

    try {
      setStage("requesting-url");
      const { document_id, upload_url } = await apiJson<{ document_id: string; upload_url: string }>(
        "/api/documents/upload-url",
        {
          method: "POST",
          body: JSON.stringify({
            knowledge_base_id: knowledgeBaseId,
            filename: file.name,
            content_type: file.type || "application/octet-stream",
            size_bytes: file.size,
          }),
        }
      );

      setStage("uploading");
      await uploadWithProgress(upload_url, file, setProgress);

      setStage("confirming");
      await apiJson("/api/documents/confirm", {
        method: "POST",
        body: JSON.stringify({ document_id }),
      });

      setStage("done");
      queryClient.invalidateQueries({ queryKey: ["documents", knowledgeBaseId] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    } catch (e) {
      setStage("error");
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  };

  return { upload, stage, progress, error };
}

/** Plain XHR (not fetch) specifically so we get upload progress events —
 * fetch's streaming upload progress support is still inconsistent across
 * browsers as of writing. */
function uploadWithProgress(url: string, file: File, onProgress: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`S3 upload failed: ${xhr.status}`)));
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(file);
  });
}

// apiFetch is imported for parity with the rest of the codebase's pattern
// even though this hook uses apiJson for the two JSON legs; kept explicit
// rather than re-exporting to avoid an unused-import lint warning silently
// masking a real accidental removal later.
void apiFetch;
