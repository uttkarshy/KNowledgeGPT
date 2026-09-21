"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, apiJson, clearTokens, getAccessToken } from "@/lib/api-client";

export function AuthBoundary({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const queries = useQueryClient();
  const protectedPage = ["/dashboard", "/chat", "/admin"].includes(path);
  const [checkedPath, setCheckedPath] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!protectedPage) return;
    let active = true;
    setError("");
    if (!getAccessToken()) { router.replace("/login"); return; }
    apiJson<{ role: string }>("/api/auth/me").then(user => {
      if (!active) return;
      if (path === "/admin" && user.role !== "admin") router.replace("/dashboard");
      else setCheckedPath(path);
    }).catch(e => {
      if (!active) return;
      if (e instanceof ApiError && [401, 403].includes(e.status)) {
        clearTokens(); queries.clear(); router.replace("/login");
      } else setError("Cannot connect to your workspace. Please refresh to retry.");
    });
    return () => { active = false; };
  }, [path, protectedPage, queries, router]);
  if (!protectedPage) return <>{children}</>;
  if (checkedPath !== path || error) return <main className="flex min-h-dvh items-center justify-center bg-canvas p-6" role="status"><div className="text-center"><div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-mist-200 border-t-stamp-teal" /><p className={`mt-4 text-sm ${error ? "text-danger" : "text-ink-500"}`}>{error || "Opening your workspace…"}</p></div></main>;
  return <>{children}</>;
}
