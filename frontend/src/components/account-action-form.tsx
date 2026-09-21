"use client";

import Link from "next/link";
import { useState } from "react";
import { apiJson } from "@/lib/api-client";
import { AuthShell } from "@/components/auth-shell";

export function AccountActionForm({ mode }: { mode: "forgot-password" | "reset-password" | "verify-email" }) {
  const [value, setValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const title = mode === "forgot-password" ? "Reset your password" : mode === "reset-password" ? "Choose a new password" : "Verify your email";
  const helper = mode === "forgot-password"
    ? "Enter your email and we’ll send reset instructions if an account exists."
    : mode === "reset-password"
      ? "Choose a strong new password for your workspace."
      : "Confirm your email address to finish setting up your workspace.";
  return <AuthShell>
    <form className="surface-card p-6 sm:p-8" onSubmit={async e => {
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
      <p className="text-sm font-semibold text-stamp-teal">Account access</p>
      <h1 className="mt-2 font-display text-3xl font-semibold tracking-[-0.03em] text-ink-950">{title}</h1>
      <p className="mt-2 text-sm leading-6 text-ink-500">{helper}</p>
      {mode !== "verify-email" && <label className="mt-4 block text-sm">
        {mode === "forgot-password" ? "Email" : "New password"}
        <input className="field-control mt-2" required type={mode === "forgot-password" ? "email" : "password"}
          autoComplete={mode === "forgot-password" ? "email" : "new-password"} value={value} onChange={e => setValue(e.target.value)} />
      </label>}
      {mode === "reset-password" && <p className="mt-2 text-xs">Use 10 or more characters with uppercase, lowercase, a number and a symbol; maximum 72 UTF-8 bytes.</p>}
      {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
      {message && <p role="status" className="mt-4 rounded-xl border border-success/20 bg-success/10 p-3 text-sm text-ink-700">{message}</p>}
      <button disabled={busy || !!message} className="primary-button mt-5 w-full">{busy ? "Working…" : "Continue"}</button>
      <Link href="/login" className="mt-5 block text-center text-sm font-medium text-stamp-teal hover:underline">Back to sign in</Link>
    </form>
  </AuthShell>;
}
