"use client";

/** Three-dot "assistant is thinking" animation. */
export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1" aria-label="Assistant is thinking">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="va-dot h-2 w-2 rounded-full bg-neutral-400 dark:bg-neutral-500"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
