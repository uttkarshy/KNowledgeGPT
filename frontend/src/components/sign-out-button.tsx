"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { apiJson, clearTokens, getRefreshToken } from "@/lib/api-client";

export function SignOutButton({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const queries = useQueryClient();

  const signOut = async () => {
    const token = getRefreshToken();
    try {
      if (token) {
        await apiJson("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: token }),
          skipAuth: true,
        });
      }
    } catch {
      // Local logout still proceeds when the server is unreachable.
    } finally {
      clearTokens();
      queries.clear();
      router.replace("/login");
    }
  };

  return (
    <button
      type="button"
      onClick={signOut}
      className={`inline-flex items-center rounded-lg text-ink-500 transition hover:bg-ink-950/[0.05] hover:text-ink-900 dark:hover:bg-white/10 dark:hover:text-white ${
        compact ? "h-9 w-9 justify-center" : "w-full gap-2.5 px-3 py-2 text-sm"
      }`}
      aria-label="Sign out"
    >
      <LogOut size={16} />
      {!compact && <span>Sign out</span>}
    </button>
  );
}
