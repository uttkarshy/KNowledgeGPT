"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, apiJson, clearTokens, getAccessToken, getRefreshToken } from "@/lib/api-client";

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
  if (checkedPath !== path || error) return <main className="p-6" role="status">{error || "Opening your workspace…"}</main>;
  return <>
    <button className="fixed right-3 top-2 z-30 rounded border bg-white px-2 py-1 text-xs" onClick={async () => {
      const token = getRefreshToken();
      try { if (token) await apiJson("/api/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: token }), skipAuth: true }); }
      catch { /* Local logout still proceeds when the server is unreachable. */ }
      finally { clearTokens(); queries.clear(); setCheckedPath(""); router.replace("/login"); }
    }}>Sign out</button>
    {children}
  </>;
}
