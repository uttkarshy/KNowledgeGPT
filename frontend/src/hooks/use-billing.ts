"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api-client";

export interface CreditSummary {
  balance: number;
  plan_code: string;
  starter_allowance: number;
  chat_credits: number;
  document_credits_per_page: number;
  payments_enabled: boolean;
}

export interface CreditUsage {
  id: string;
  operation: string | null;
  credits_delta: number;
  input_tokens: number;
  output_tokens: number;
  model: string | null;
  created_at: string;
}

export function useCredits() {
  return useQuery({ queryKey: ["credits"], queryFn: () => apiJson<CreditSummary>("/api/billing/credits"), staleTime: 5000 });
}

export function useCreditUsage() {
  return useQuery({ queryKey: ["credit-usage"], queryFn: () => apiJson<CreditUsage[]>("/api/billing/usage?limit=5") });
}
