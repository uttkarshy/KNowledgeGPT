import { Sparkles } from "lucide-react";

interface BrandProps {
  compact?: boolean;
  inverse?: boolean;
}

export function Brand({ compact = false, inverse = false }: BrandProps) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-xl ${
          inverse ? "bg-white/10 text-white" : "bg-stamp-teal text-white shadow-sm shadow-stamp-teal/20"
        }`}
        aria-hidden="true"
      >
        <Sparkles size={15} strokeWidth={1.8} />
      </span>
      {!compact && (
        <span className={`font-display text-lg font-semibold tracking-[-0.02em] ${inverse ? "text-white" : "text-ink-950 dark:text-white"}`}>
          KnowledgeGPT
        </span>
      )}
    </div>
  );
}
