"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiJson, setTokens } from "@/lib/api-client";
export default function Page() {
  const started = useRef(false); const [error, setError] = useState(""); const router = useRouter();
  useEffect(() => {
    if (started.current) return; started.current = true;
    const params = new URLSearchParams(window.location.search);
    apiJson<{access_token: string; refresh_token: string}>("/api/auth/google/callback", {
      method: "POST", skipAuth: true, body: JSON.stringify({code: params.get("code"), state: params.get("state")})
    }).then(tokens => { setTokens(tokens.access_token, tokens.refresh_token); router.replace("/dashboard"); })
      .catch(e => setError(e instanceof Error ? e.message : "Sign-in failed"));
  }, [router]);
  return <main className="p-6">{error || "Completing sign-in…"}{error && <Link href="/login" className="block text-stamp-teal">Return to sign in</Link>}</main>;
}
