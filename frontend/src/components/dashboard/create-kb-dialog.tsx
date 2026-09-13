"use client";

import { useState } from "react";
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 px-4">
      <div className="w-full max-w-md rounded-lg border border-mist-200 bg-white p-5 shadow-xl dark:border-ink-700 dark:bg-ink-900">
        <h2 className="font-display text-lg text-ink-900 dark:text-mist-50">New knowledge base</h2>

        <form onSubmit={handleSubmit} className="mt-4">
          {createKB.error && <p role="alert" className="mb-3 text-sm text-danger">{createKB.error.message}</p>}
          <label className="block text-sm font-medium text-ink-700 dark:text-mist-100">
            Name
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-mist-200 bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-stamp-teal dark:border-ink-700"
              placeholder="e.g. Product Documentation"
            />
          </label>

          <label className="mt-3 block text-sm font-medium text-ink-700 dark:text-mist-100">
            Description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full resize-none rounded-md border border-mist-200 bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-stamp-teal dark:border-ink-700"
              placeholder="Optional"
            />
          </label>

          <div className="mt-3">
            <span className="text-sm font-medium text-ink-700 dark:text-mist-100">Color</span>
            <div className="mt-1.5 flex gap-2">
              {COLOR_SWATCHES.map((swatch) => (
                <button
                  key={swatch}
                  type="button"
                  onClick={() => setColor(swatch)}
                  aria-label={`Choose color ${swatch}`}
                  className="h-6 w-6 rounded-full ring-offset-2 transition"
                  style={{
                    backgroundColor: swatch,
                    boxShadow: color === swatch ? `0 0 0 2px white, 0 0 0 4px ${swatch}` : undefined,
                  }}
                />
              ))}
            </div>
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-3 py-1.5 text-sm text-ink-500 hover:bg-mist-100 dark:hover:bg-ink-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createKB.isPending || !name.trim()}
              className="rounded-md bg-stamp-teal px-4 py-1.5 text-sm font-medium text-white hover:bg-stamp-tealDark disabled:opacity-60"
            >
              {createKB.isPending ? "Creating…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
