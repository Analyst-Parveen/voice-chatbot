"use client";

import { cn } from "../lib/cn";
import type { ChatLanguage } from "../lib/types";

interface Props {
  languages: ChatLanguage[];
  onSelect: (lang: ChatLanguage) => void;
  onBack: () => void;
}

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
      <div className="grid gap-2">
        {languages.map((lang) => (
          <button
            key={lang.id}
            type="button"
            onClick={() => onSelect(lang)}
            className={cn(
              "w-full rounded-xl border px-4 py-3 text-left transition-all",
              "border-neutral-200 dark:border-neutral-700",
              "hover:border-[var(--va-accent)] hover:bg-[var(--va-accent)]/5",
            )}
          >
            <span className="font-medium">{lang.label}</span>
            <span className="block text-xs text-neutral-500 mt-0.5">{lang.nativeLabel}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
