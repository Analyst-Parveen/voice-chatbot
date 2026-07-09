"use client";

import { cn } from "../lib/cn";
import type { ChatLanguage } from "../lib/types";

interface Props {
  languages: ChatLanguage[];
  onSelect: (lang: ChatLanguage) => void;
  onBack: () => void;
}

/** Per-language color themes (matched to the mode-selector card style). */
const LANGUAGE_STYLES: Record<
  string,
  { card: string; badge: string; label: string; icon: string }
> = {
  "en-IN": {
    card:
      "border-cyan-400/70 dark:border-cyan-400/50 ring-2 ring-cyan-400/20 " +
      "bg-gradient-to-br from-cyan-100 to-sky-100 dark:from-cyan-900/50 dark:to-sky-900/40",
    badge: "bg-gradient-to-br from-cyan-500 to-sky-600",
    label: "text-cyan-900 dark:text-cyan-100",
    icon: "EN",
  },
  "hi-IN": {
    card:
      "border-amber-400/70 dark:border-amber-400/50 ring-2 ring-amber-400/20 " +
      "bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-900/50 dark:to-orange-900/40",
    badge: "bg-gradient-to-br from-amber-500 to-orange-600",
    label: "text-amber-900 dark:text-amber-100",
    icon: "अ",
  },
};

const DEFAULT_LANGUAGE_STYLE = {
  card:
    "border-indigo-400/70 dark:border-indigo-400/50 ring-2 ring-indigo-400/20 " +
    "bg-gradient-to-br from-indigo-100 to-violet-100 dark:from-indigo-900/50 dark:to-violet-900/40",
  badge: "bg-gradient-to-br from-indigo-500 to-violet-600",
  label: "text-indigo-900 dark:text-indigo-100",
  icon: "🌐",
};

export function LanguageSelector({ languages, onSelect, onBack }: Props) {
  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <button
        type="button"
        onClick={onBack}
        className="text-xs text-neutral-500 hover:text-[var(--va-accent)] mb-4"
      >
        ← Back
      </button>
      <div className="text-center mb-5">
        <p className="text-lg font-semibold tracking-tight">
          Please select your preferred language
        </p>
        <p className="mt-1 text-sm text-neutral-500">
          Hindi supports Devanagari and Roman Hinglish (WhatsApp style)
        </p>
      </div>
      <div className="grid gap-3">
        {languages.map((lang) => {
          const style = LANGUAGE_STYLES[lang.id] ?? DEFAULT_LANGUAGE_STYLE;
          return (
            <button
              key={lang.id}
              type="button"
              onClick={() => onSelect(lang)}
              className={cn(
                "w-full rounded-2xl border-2 px-4 py-3.5 text-left transition-all",
                "hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]",
                style.card,
              )}
            >
              <span className="flex items-center gap-3">
                <span
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg font-bold text-white shadow",
                    style.badge,
                  )}
                >
                  {style.icon}
                </span>
                <span>
                  <span className={cn("block font-bold", style.label)}>{lang.label}</span>
                  <span className="block text-xs text-neutral-600 dark:text-neutral-300 mt-0.5">
                    {lang.nativeLabel}
                  </span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
