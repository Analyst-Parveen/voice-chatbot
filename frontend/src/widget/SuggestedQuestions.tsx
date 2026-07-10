"use client";

/** Clickable starter-question chips shown on an empty conversation. */
export function SuggestedQuestions({
  suggestions,
  onSelect,
  sectionLabel = "Suggested questions",
}: {
  suggestions: string[];
  onSelect: (q: string) => void;
  sectionLabel?: string;
}) {
  if (suggestions.length === 0) return null;
  return (
    <div className="px-4 pb-3">
      <p className="text-xs text-neutral-500 mb-2">{sectionLabel}</p>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onSelect(q)}
            className="text-xs text-left rounded-full border border-neutral-200 dark:border-neutral-700 px-3 py-1.5 hover:border-[var(--va-accent)] hover:text-[var(--va-accent)] transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
