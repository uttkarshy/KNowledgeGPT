"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useCreateKnowledgeBase } from "@/hooks/use-knowledge-bases";

interface CreateKBDialogProps {
  open: boolean;
  onClose: () => void;
}

const COLOR_SWATCHES = ["#146661", "#D98E2B", "#5E8F6B", "#B5493D", "#2A2E35", "#1C8983"];

export function CreateKBDialog({ open, onClose }: CreateKBDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState(COLOR_SWATCHES[0]);
  const createKB = useCreateKnowledgeBase();

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try { await createKB.mutateAsync({ name: name.trim(), description: description.trim() || undefined, color }); } catch { return; }
    setName("");
    setDescription("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/45 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="create-kb-title">
      <div className="w-full max-w-lg rounded-2xl border border-white/20 bg-white p-6 shadow-float dark:border-white/10 dark:bg-ink-900 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="create-kb-title" className="font-display text-2xl font-semibold tracking-[-0.02em] text-ink-950 dark:text-white">New knowledge base</h2>
            <p className="mt-1 text-sm text-ink-500">Create a focused home for related documents.</p>
          </div>
          <button type="button" onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-500 hover:bg-mist-50" aria-label="Close dialog"><X size={18} /></button>
        </div>

        <form onSubmit={handleSubmit} className="mt-6">
          {createKB.error && <p role="alert" className="mb-3 text-sm text-danger">{createKB.error.message}</p>}
          <label className="block text-sm font-medium text-ink-700 dark:text-mist-100">
            Name
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="field-control mt-2"
              placeholder="e.g. Product documentation"
            />
          </label>

          <label className="mt-3 block text-sm font-medium text-ink-700 dark:text-mist-100">
            Description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="field-control mt-2 resize-none"
              placeholder="What kind of documents will live here? (optional)"
            />
          </label>

          <div className="mt-4">
            <span className="text-sm font-medium text-ink-700 dark:text-mist-100">Color</span>
            <div className="mt-2 flex gap-3">
              {COLOR_SWATCHES.map((swatch) => (
                <button
                  key={swatch}
                  type="button"
                  onClick={() => setColor(swatch)}
                  aria-label={`Choose color ${swatch}`}
                  className="h-7 w-7 rounded-full ring-offset-2 transition hover:scale-110"
                  style={{
                    backgroundColor: swatch,
                    boxShadow: color === swatch ? `0 0 0 2px white, 0 0 0 4px ${swatch}` : undefined,
                  }}
                />
              ))}
            </div>
          </div>

          <div className="mt-7 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="secondary-button"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createKB.isPending || !name.trim()}
              className="primary-button"
            >
              {createKB.isPending ? "Creating…" : "Create knowledge base"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
