"use client";

import { ArrowDown, ArrowUp, Coins, Loader2, X } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useCredits, useCreditUsage } from "@/hooks/use-billing";
import { apiJson } from "@/lib/api-client";

interface CreditPack { code: string; credits: number; amount_paise: number }
interface RazorpayOrder { order_id: string; amount_paise: number; currency: string; key_id: string }

declare global {
  interface Window { Razorpay?: new (options: Record<string, unknown>) => { open: () => void } }
}

async function loadRazorpay(): Promise<void> {
  if (window.Razorpay) return;
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Could not load secure checkout"));
    document.head.appendChild(script);
  });
}

export function CreditsCard() {
  const credits = useCredits();
  const usage = useCreditUsage();
  const queryClient = useQueryClient();
  const [packs, setPacks] = useState<CreditPack[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingPacks, setLoadingPacks] = useState(false);
  const [buyingCode, setBuyingCode] = useState<string | null>(null);
  const buy = async (pack: CreditPack) => {
    try {
      setError(null);
      setBuyingCode(pack.code);
      const order = await apiJson<RazorpayOrder>("/api/billing/orders", {
        method: "POST", body: JSON.stringify({ pack_code: pack.code }),
      });
      await loadRazorpay();
      const Razorpay = window.Razorpay;
      if (!Razorpay) throw new Error("Secure checkout did not initialize");
      const checkout = new Razorpay({
        key: order.key_id, order_id: order.order_id, amount: order.amount_paise,
        currency: order.currency, name: "KnowledgeGPT", description: `${pack.credits} credits`,
        handler: () => {
          setPacks(null);
          setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: ["credits"] });
            queryClient.invalidateQueries({ queryKey: ["credit-usage"] });
          }, 1500);
        },
      });
      checkout.open();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Checkout could not start");
    } finally {
      setBuyingCode(null);
    }
  };
  const showPacks = async () => {
    try {
      setError(null);
      setLoadingPacks(true);
      setPacks(await apiJson<CreditPack[]>("/api/billing/packs"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Credit packs are unavailable");
    } finally {
      setLoadingPacks(false);
    }
  };
  if (!credits.data) return null;
  return (
    <section id="credits" className="surface-card overflow-hidden">
      <div className="p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink-950 dark:text-white"><Coins size={16} className="text-stamp-teal" /> Credits</div>
        <div className="mt-4 flex items-end justify-between gap-4">
          <div>
            <p className="font-display text-4xl font-semibold tracking-[-0.04em] text-ink-950 dark:text-white">{credits.data.balance}</p>
            <p className="mt-1 text-xs text-ink-500">available to use</p>
          </div>
          <button disabled={!credits.data.payments_enabled || loadingPacks} title={credits.data.payments_enabled ? undefined : "Payments are not configured yet"}
            onClick={showPacks}
            className="secondary-button px-3 py-2 text-xs">
            {loadingPacks ? <Loader2 size={14} className="animate-spin" /> : "Buy credits"}
          </button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-mist-50 p-3 text-xs dark:bg-ink-800">
          <div><span className="block font-semibold text-ink-900 dark:text-white">1 credit</span><span className="text-ink-500">per answer</span></div>
          <div><span className="block font-semibold text-ink-900 dark:text-white">{credits.data.document_credits_per_page} credit</span><span className="text-ink-500">per document page</span></div>
        </div>
      </div>
      {error && <p role="alert" className="mx-5 mb-4 rounded-lg bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>}
      {usage.data && usage.data.length > 0 && (
        <div className="border-t border-ink-950/[0.06] px-5 py-4 dark:border-white/10">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-300">Recent usage</p>
          <div className="mt-2 space-y-2">
            {usage.data.slice(0, 3).map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-3 text-xs">
                <span className="flex min-w-0 items-center gap-2 text-ink-500">
                  {item.credits_delta < 0 ? <ArrowDown size={12} /> : <ArrowUp size={12} />}
                  <span className="truncate capitalize">{item.operation?.replaceAll(".", " ") || "Credit activity"}</span>
                </span>
                <span className={`font-mono font-medium ${item.credits_delta < 0 ? "text-ink-700 dark:text-mist-100" : "text-success"}`}>{item.credits_delta > 0 ? "+" : ""}{item.credits_delta}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {!credits.data.payments_enabled && <p className="border-t border-ink-950/[0.06] px-5 py-3 text-xs leading-5 text-ink-500">Credit purchases are opening soon. Your starter credits remain available.</p>}

      {packs && (
        <div className="fixed inset-0 z-[70] flex items-end justify-center bg-ink-950/45 p-0 backdrop-blur-sm sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby="credit-packs-title">
          <div className="w-full max-w-lg rounded-t-2xl border border-white/20 bg-white p-6 shadow-float dark:border-white/10 dark:bg-ink-900 sm:rounded-2xl sm:p-7">
            <div className="flex items-start justify-between gap-4">
              <div><p className="text-sm font-semibold text-stamp-teal">Keep asking</p><h2 id="credit-packs-title" className="mt-1 font-display text-2xl font-semibold text-ink-950 dark:text-white">Add credits</h2><p className="mt-1 text-sm text-ink-500">Secure payment powered by Razorpay.</p></div>
              <button type="button" onClick={() => setPacks(null)} className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-500 hover:bg-mist-50" aria-label="Close credit packs"><X size={18} /></button>
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">{packs.map((pack) => (
              <button key={pack.code} onClick={() => buy(pack)} disabled={buyingCode !== null} className="group rounded-2xl border border-ink-950/10 p-5 text-left transition hover:border-stamp-teal hover:bg-stamp-teal/[0.03] disabled:opacity-60 dark:border-white/10">
                <span className="block font-display text-3xl font-semibold text-ink-950 dark:text-white">{pack.credits}</span>
                <span className="mt-1 block text-xs text-ink-500">credits</span>
                <span className="mt-5 flex items-center justify-between text-sm font-semibold text-stamp-teal"><span>₹{(pack.amount_paise / 100).toFixed(0)}</span>{buyingCode === pack.code ? <Loader2 size={15} className="animate-spin" /> : <span>Choose →</span>}</span>
              </button>
            ))}</div>
            <p className="mt-5 text-center text-xs leading-5 text-ink-500">Credits are added after secure payment confirmation. No credits are granted from the browser.</p>
          </div>
        </div>
      )}
    </section>
  );
}
