"use client";

/** Animated bars whose height reflects the live mic input level (0..1). */
export function VoiceWave({ level }: { level: number }) {
  const bars = [0.4, 0.7, 1, 0.7, 0.4];
  return (
    <div className="flex items-center gap-0.5 h-5" aria-hidden>
      {bars.map((weight, i) => {
        const h = Math.max(0.15, Math.min(1, level * weight * 1.6));
        return (
          <span
            key={i}
            className="w-0.5 rounded-full bg-current transition-[height] duration-75"
            style={{ height: `${h * 100}%` }}
          />
        );
      })}
    </div>
  );
}
