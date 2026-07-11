"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api-client";
import type { KnowledgeBase } from "@/types";

export function useKnowledgeBases(search?: string) {
  return useQuery({
    queryKey: ["knowledge-bases", search ?? ""],
    queryFn: () =>
      apiJson<KnowledgeBase[]>(`/api/knowledge-bases${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  });
}

export interface CreateKBInput {
  name: string;
  description?: string;
  color?: string;
  icon?: string;
  tags?: string[];
}

export function useCreateKnowledgeBase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateKBInput) =>
      apiJson<KnowledgeBase>("/api/knowledge-bases", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] }),
  });
}

export function useArchiveKnowledgeBase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson<KnowledgeBase>(`/api/knowledge-bases/${id}/archive`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] }),
  });
}

export function useDuplicateKnowledgeBase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson<KnowledgeBase>(`/api/knowledge-bases/${id}/duplicate`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] }),
  });
}

export function useDeleteKnowledgeBase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson<void>(`/api/knowledge-bases/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] }),
  });
}
