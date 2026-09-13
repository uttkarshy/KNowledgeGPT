"use client";

import Link from "next/link";
import { useState } from "react";
import { apiJson } from "@/lib/api-client";

export function AccountActionForm({ mode }: { mode: "forgot-password" | "reset-password" | "verify-email" }) {
  const [value, setValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const title = mode === "forgot-password" ? "Reset your password" : mode === "reset-password" ? "Choose a new password" : "Verify your email";
  return <main className="flex min-h-screen items-center justify-center bg-mist-50 px-4">
    <form className="w-full max-w-sm rounded-lg border bg-white p-6" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError("");
      try {
        const token = new URLSearchParams(window.location.search).get("token");
        if (mode !== "forgot-password" && !token) throw new Error("The link is missing its token. Request a new link.");
        await apiJson(`/api/auth/${mode}`, { method: "POST", skipAuth: true, body: JSON.stringify(
          mode === "forgot-password" ? { email: value } : mode === "reset-password" ? { token, new_password: value } : { token }
        ) });
        setMessage(mode === "forgot-password" ? "If an account exists and email delivery is configured, a reset link will be sent." : "Done. You can now sign in.");
      } catch (e) { setError(e instanceof Error ? e.message : "Please try again."); }
      finally { setBusy(false); }
    }}>
      <h1 className="font-display text-xl">{title}</h1>
      {mode !== "verify-email" && <label className="mt-4 block text-sm">
        {mode === "forgot-password" ? "Email" : "New password"}
        <input className="mt-2 w-full rounded border px-3 py-2" required type={mode === "forgot-password" ? "email" : "password"}
          autoComplete={mode === "forgot-password" ? "email" : "new-password"} value={value} onChange={e => setValue(e.target.value)} />
      </label>}
      {mode === "reset-password" && <p className="mt-2 text-xs">Use 10 or more characters with uppercase, lowercase, a number and a symbol; maximum 72 UTF-8 bytes.</p>}
      {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
      {message && <p role="status" className="mt-3 text-sm">{message}</p>}
      <button disabled={busy || !!message} className="mt-4 w-full rounded bg-stamp-teal p-2 text-white disabled:opacity-50">{busy ? "Working…" : "Continue"}</button>
      <Link href="/login" className="mt-4 block text-sm text-stamp-teal">Back to sign in</Link>
    </form>
  </main>;
}
