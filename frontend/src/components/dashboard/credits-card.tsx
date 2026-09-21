"use client";

import { Coins } from "lucide-react";
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
  const buy = async (pack: CreditPack) => {
    try {
      setError(null);
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
    }
  };
  const showPacks = async () => {
    try { setError(null); setPacks(await apiJson<CreditPack[]>("/api/billing/packs")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Credit packs are unavailable"); }
  };
  if (!credits.data) return null;
  return (
    <section className="mt-5 rounded-md border border-mist-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium"><Coins size={16} /> KnowledgeGPT Credits</div>
          <p className="mt-1 font-display text-2xl">{credits.data.balance}</p>
          <p className="text-xs text-ink-500">1 per answer · {credits.data.document_credits_per_page} per document page</p>
        </div>
        <button disabled={!credits.data.payments_enabled} title={credits.data.payments_enabled ? undefined : "Payments are not configured yet"}
          onClick={showPacks}
          className="rounded-md bg-stamp-teal px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50">
          Buy credits
        </button>
      </div>
      {packs && <div className="mt-3 flex flex-wrap gap-2">{packs.map((pack) => (
        <button key={pack.code} onClick={() => buy(pack)} className="rounded border border-stamp-teal px-3 py-2 text-xs text-stamp-teal">
          {pack.credits} credits · ₹{(pack.amount_paise / 100).toFixed(0)}
        </button>
      ))}</div>}
      {error && <p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
      {usage.data && usage.data.length > 0 && (
        <div className="mt-3 border-t border-mist-200 pt-2 text-xs text-ink-500 dark:border-ink-700">
          Recent: {usage.data.slice(0, 3).map((item) => `${item.operation?.replace(".", " ")} ${item.credits_delta}`).join(" · ")}
        </div>
      )}
      {!credits.data.payments_enabled && <p className="mt-2 text-xs text-ink-500">Credit purchases are opening soon. Your starter credits remain available.</p>}
    </section>
  );
}
