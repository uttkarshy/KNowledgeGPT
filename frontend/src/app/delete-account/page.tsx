"use client";

import { FormEvent, useState } from "react";
import { apiJson } from "@/lib/api-client";

export default function DeleteAccount() {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = new FormData(e.currentTarget).get("email");
    setBusy(true);
    try {
      const result = await apiJson<{ reference: string }>("/api/support/deletion-request", {
        method: "POST", skipAuth: true, body: JSON.stringify({ email, confirmation: "DELETE" })
      });
      setStatus("Request received. Keep reference " + result.reference + ". Support will verify your email before erasure.");
    } catch { setStatus("Your request could not be confirmed. Please try again later."); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto max-w-xl space-y-5 p-8"><h1 className="text-3xl font-bold">Delete your KnowledgeGPT account</h1>
    <p>Request deletion from UtkarshLabs using your account email. After verifying control of the address, support removes the account, documents, indexed passages, conversations and sessions. Restricted backups expire under the operator’s retention policy.</p>
    <form onSubmit={submit} className="grid gap-4"><label>Account email <input className="border p-2" name="email" type="email" required /></label>
    <label><input type="checkbox" required /> I request deletion of this account and its associated data.</label>
    <button disabled={busy} className="rounded bg-teal-800 p-3 text-white">{busy ? "Sending…" : "Request account deletion"}</button></form><p role="status">{status}</p></main>;
}
