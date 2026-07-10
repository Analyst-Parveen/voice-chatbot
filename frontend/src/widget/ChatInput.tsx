"use client";

import { useEffect, useRef } from "react";

import { cn } from "../lib/cn";
import { VoiceButton } from "./VoiceButton";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  disabled?: boolean;
  voiceEnabled: boolean;
  isListening?: boolean;
  /** True while the assistant is replying — shows Stop instead of Send. */
  streaming?: boolean;
  /** Called when the user presses Stop during a reply. */
  onStopStreaming?: () => void;
  /** Optional Hindi/localized placeholders when Hindi mode is active. */
  placeholder?: string;
  listeningPlaceholder?: string;
  listeningHint?: string;
  voice: {
    isRecording: boolean;
    level: number;
    supported: boolean;
    onStart: () => void;
    onStop: () => void;
  };
}

export function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
  voiceEnabled,
  isListening,
  streaming,
  onStopStreaming,
  placeholder = "Type your message…",
  listeningPlaceholder = "Your speech appears here…",
  listeningHint = "Listening… text updates every few seconds",
  voice,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const grow = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  };

  useEffect(() => {
    grow();
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    onChange("");
    requestAnimationFrame(() => {
      if (taRef.current) taRef.current.style.height = "auto";
    });
  };

  return (
    <div className="border-t border-neutral-200 dark:border-neutral-800 p-2.5 bg-white/80 dark:bg-neutral-900/80 backdrop-blur-sm">
      {isListening && (
        <div className="mb-1.5 flex items-center gap-2 px-1 text-[11px] text-[var(--va-accent)] animate-pulse">
          <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
          {listeningHint}
        </div>
      )}
      <div className="flex items-end gap-1.5">
        <textarea
          ref={taRef}
          rows={1}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            grow();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={isListening ? listeningPlaceholder : placeholder}
          className={cn(
            "flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-neutral-400 max-h-[120px]",
            isListening && "ring-1 ring-[var(--va-accent)]/40 rounded-lg",
          )}
        />
        {voiceEnabled && voice.supported && (
          <VoiceButton
            isRecording={voice.isRecording}
            level={voice.level}
            disabled={disabled}
            onStart={voice.onStart}
            onStop={voice.onStop}
          />
        )}
        {streaming && onStopStreaming ? (
          <button
            type="button"
            onClick={onStopStreaming}
            aria-label="Stop response"
            title="Stop response"
            className="va-send-btn flex items-center justify-center h-9 w-9 rounded-full text-white transition-all hover:scale-105 active:scale-95 bg-red-500"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={disabled || value.trim().length === 0}
            aria-label="Send"
            className="va-send-btn flex items-center justify-center h-9 w-9 rounded-full text-white disabled:opacity-40 transition-all hover:scale-105 active:scale-95"
            style={{ backgroundColor: "var(--va-accent)" }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
