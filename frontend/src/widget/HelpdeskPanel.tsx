"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "../lib/cn";
import type { HelpdeskStep } from "../lib/types";

interface Props {
  step: HelpdeskStep | null;
  turns: { role: "user" | "assistant"; content: string }[];
  loading: boolean;
  completed: boolean;
  error: string | null;
  onRespond: (answer: string, displayLabel?: string) => void;
  onBack: () => void;
}

export function HelpdeskPanel({
  step,
  turns,
  loading,
  completed,
  error,
  onRespond,
  onBack,
}: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, step]);

  useEffect(() => {
    setDraft("");
  }, [step?.step_id]);

  const submitText = () => {
    if (!draft.trim() || loading || completed) return;
    onRespond(draft);
    setDraft("");
  };

  const progress = step?.progress ?? (completed ? 100 : 0);

  return (
    <div className="flex flex-1 flex-col min-h-0">
      <div className="px-4 pt-2 pb-1 flex items-center gap-2">
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
        >
          ← Back
        </button>
        <div className="flex-1 h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 va-helpdesk-progress"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-[10px] text-neutral-400 w-8 text-right">{progress}%</span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {turns.map((t, i) => (
          <div
            key={i}
            className={cn(
              "max-w-[90%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed animate-[va-fade-in_0.25s_ease]",
              t.role === "user"
                ? "ml-auto text-white rounded-br-sm"
                : "bg-neutral-100 dark:bg-neutral-800 rounded-bl-sm",
            )}
            style={t.role === "user" ? { backgroundColor: "var(--va-accent)" } : undefined}
          >
            <span className="whitespace-pre-wrap">{t.content}</span>
          </div>
        ))}
        {loading && (
          <div className="text-xs text-neutral-400 animate-pulse px-1">Processing…</div>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <div className="px-4 py-1 text-xs text-center text-red-500 bg-red-50 dark:bg-red-950/30">
          {error}
        </div>
      )}

      {!completed && step && (
        <div className="border-t border-neutral-200 dark:border-neutral-800 p-3 space-y-2">
          {step.field_type === "choice" && step.options.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {step.options.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  disabled={loading}
                  onClick={() => onRespond(opt.id, opt.label)}
                  className={cn(
                    "va-helpdesk-chip px-3 py-2 rounded-xl text-xs font-medium transition-all",
                    "border border-neutral-200 dark:border-neutral-700",
                    "hover:border-[var(--va-accent)] hover:text-[var(--va-accent)]",
                    "disabled:opacity-40",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex items-end gap-2">
              {step.field_type === "textarea" ? (
                <textarea
                  rows={2}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      submitText();
                    }
                  }}
                  placeholder={step.placeholder ?? "Type your answer…"}
                  disabled={loading}
                  className="flex-1 resize-none rounded-xl border border-neutral-200 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--va-accent)]/30"
                />
              ) : (
                <input
                  type={step.field_type === "phone" || step.field_type === "number" ? "tel" : "text"}
                  inputMode={step.field_type === "phone" ? "numeric" : undefined}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submitText()}
                  placeholder={step.placeholder ?? "Type your answer…"}
                  disabled={loading}
                  className="flex-1 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--va-accent)]/30"
                />
              )}
              <button
                type="button"
                onClick={submitText}
                disabled={loading || !draft.trim()}
                className="h-10 px-4 rounded-xl text-sm font-medium text-white disabled:opacity-40 transition-opacity"
                style={{ backgroundColor: "var(--va-accent)" }}
              >
                Submit
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
