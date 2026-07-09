"use client";

import { cn } from "../lib/cn";

interface Props {
  onSelect: (mode: "helpdesk" | "query") => void;
}

export function ModeSelector({ onSelect }: Props) {
  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="text-center mb-6">
        <p className="text-lg font-semibold tracking-tight">How can we help?</p>
        <p className="mt-1 text-sm text-neutral-500">Choose a path to get started</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => onSelect("helpdesk")}
          className={cn(
            "va-mode-card group text-left rounded-2xl p-4 border-2 transition-all",
            "border-indigo-400/70 dark:border-indigo-400/50",
            "bg-gradient-to-br from-indigo-100 to-violet-100 dark:from-indigo-900/50 dark:to-violet-900/40",
            "hover:shadow-xl hover:scale-[1.03] active:scale-[0.98]",
            "ring-2 ring-indigo-400/20",
          )}
        >
          <div className="flex flex-col items-center text-center gap-2">
            <span className="va-mode-icon bg-indigo-500 text-white text-2xl">🎧</span>
            <p className="font-bold text-lg text-indigo-900 dark:text-indigo-100">Helpdesk</p>
            <p className="text-xs leading-relaxed text-neutral-600 dark:text-neutral-300">
              Registration · Claims · Tracking · Support wizard
            </p>
          </div>
        </button>

        <button
          type="button"
          onClick={() => onSelect("query")}
          className={cn(
            "va-mode-card group text-left rounded-2xl p-4 border-2 transition-all",
            "border-cyan-400/70 dark:border-cyan-400/50",
            "bg-gradient-to-br from-cyan-100 to-sky-100 dark:from-cyan-900/50 dark:to-sky-900/40",
            "hover:shadow-xl hover:scale-[1.03] active:scale-[0.98]",
            "ring-2 ring-cyan-400/20",
          )}
        >
          <div className="flex flex-col items-center text-center gap-2">
            <span className="va-mode-icon bg-cyan-500 text-white text-2xl">💬</span>
            <p className="font-bold text-lg text-cyan-900 dark:text-cyan-100">Ask a Query</p>
            <p className="text-xs leading-relaxed text-neutral-600 dark:text-neutral-300">
              Voice &amp; text AI chat — type, speak, or send
            </p>
          </div>
        </button>
      </div>
    </div>
  );
}
