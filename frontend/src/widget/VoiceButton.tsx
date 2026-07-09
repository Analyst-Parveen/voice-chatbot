"use client";

import { cn } from "../lib/cn";
import { VoiceWave } from "./VoiceWave";

export function VoiceButton({
  isRecording,
  level,
  disabled,
  onStart,
  onStop,
}: {
  isRecording: boolean;
  level: number;
  disabled?: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => (isRecording ? onStop() : onStart())}
      aria-label={isRecording ? "Stop recording" : "Start voice input"}
      className={cn(
        "flex items-center justify-center h-9 w-9 rounded-full transition-colors disabled:opacity-40",
        isRecording
          ? "text-white"
          : "text-neutral-500 hover:text-[var(--va-accent)]",
      )}
      style={isRecording ? { backgroundColor: "var(--va-accent)" } : undefined}
    >
      {isRecording ? (
        <VoiceWave level={level} />
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8" />
        </svg>
      )}
    </button>
  );
}
