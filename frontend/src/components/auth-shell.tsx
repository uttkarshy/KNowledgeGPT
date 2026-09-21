import { CheckCircle2, Quote } from "lucide-react";
import Link from "next/link";
import { Brand } from "@/components/brand";

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-dvh bg-canvas lg:grid-cols-[minmax(0,1fr)_minmax(28rem,0.82fr)]">
      <section className="relative hidden overflow-hidden bg-ink-950 px-10 py-10 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 auth-grid opacity-30" aria-hidden="true" />
        <div className="relative z-10">
          <Brand inverse />
        </div>
        <div className="relative z-10 my-auto max-w-xl py-16">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs font-medium text-mist-100">
            <Quote size={13} /> Answers grounded in your sources
          </div>
          <h1 className="max-w-lg font-display text-5xl font-semibold leading-[1.08] tracking-[-0.04em]">
            Talk to your knowledge.
          </h1>
          <p className="mt-5 max-w-lg text-lg leading-8 text-mist-200">
            Upload your documents, ask natural questions, and inspect the exact evidence behind every answer.
          </p>
          <div className="mt-9 grid max-w-lg gap-3 text-sm text-mist-100 sm:grid-cols-2">
            {["PDFs and documents", "Page-level citations", "Clear processing status", "100 starter credits"].map((item) => (
              <div key={item} className="flex items-center gap-2.5">
                <CheckCircle2 size={16} className="text-stamp-tealLight" />
                {item}
              </div>
            ))}
          </div>
        </div>
        <p className="relative z-10 text-xs text-ink-300">KnowledgeGPT · Beta</p>
      </section>

      <section className="flex min-h-dvh items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <Link href="/" className="mb-10 inline-flex lg:hidden" aria-label="KnowledgeGPT home">
            <Brand />
          </Link>
          {children}
        </div>
      </section>
    </main>
  );
}
