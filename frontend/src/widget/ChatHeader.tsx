"use client";

import { cn } from "../lib/cn";

interface Props {
  title: string;
  subtitle: string;
  connected: boolean;
  voiceEnabled: boolean;
  muted: boolean;
  effectiveTheme: "light" | "dark";
  onToggleMute: () => void;
  onToggleTheme: () => void;
  onClear: () => void;
  onClose: () => void;
}

export function ChatHeader({
  title,
  subtitle,
  connected,
  voiceEnabled,
  muted,
  effectiveTheme,
  onToggleMute,
  onToggleTheme,
  onClear,
  onClose,
}: Props) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 text-white"
      style={{ backgroundColor: "var(--va-accent)" }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold truncate">{title}</span>
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              connected ? "bg-green-300" : "bg-white/40",
            )}
            title={connected ? "Connected" : "Reconnecting…"}
          />
        </div>
        <p className="text-xs text-white/80 truncate">{subtitle}</p>
      </div>

      <div className="flex items-center gap-1 text-white/90">
        {voiceEnabled && (
          <IconButton label={muted ? "Unmute voice" : "Mute voice"} onClick={onToggleMute}>
            {muted ? "🔇" : "🔊"}
          </IconButton>
        )}
        <IconButton
          label="Toggle theme"
          onClick={onToggleTheme}
        >
          {effectiveTheme === "dark" ? "☀️" : "🌙"}
        </IconButton>
        <IconButton label="Clear conversation" onClick={onClear}>
          🗑️
        </IconButton>
        <IconButton label="Close" onClick={onClose}>
          ✕
        </IconButton>
      </div>
    </div>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="h-7 w-7 rounded-md hover:bg-white/20 transition-colors text-sm leading-none"
    >
      {children}
    </button>
  );
}
