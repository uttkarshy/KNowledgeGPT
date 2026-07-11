"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api-client";
import type { AdminUser, AnalyticsSummary, ApiUsageLogEntry } from "@/types";

export function useAdminUsers(search: string) {
  return useQuery({
    queryKey: ["admin-users", search],
    queryFn: () => apiJson<AdminUser[]>(`/api/admin/users${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  });
}

export function useAnalytics() {
  return useQuery({
    queryKey: ["admin-analytics"],
    queryFn: () => apiJson<AnalyticsSummary>("/api/admin/analytics"),
    refetchInterval: 30_000,
  });
}

export function useErrorLogs() {
  return useQuery({
    queryKey: ["admin-error-logs"],
    queryFn: () => apiJson<ApiUsageLogEntry[]>("/api/admin/logs/errors?limit=50"),
  });
}

export function useSuspendUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson<AdminUser>(`/api/admin/users/${id}/suspend`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
}

export function useUnsuspendUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson<AdminUser>(`/api/admin/users/${id}/unsuspend`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiJson<void>(`/api/admin/users/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
}
