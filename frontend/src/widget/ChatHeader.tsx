"use client";

import { cn } from "../lib/cn";

interface Props {
  title: string;
  subtitle: string;
  connected: boolean;
  voiceEnabled: boolean;
  muted: boolean;
  effectiveTheme: "light" | "dark";
  fullscreen: boolean;
  onToggleFullscreen: () => void;
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
  fullscreen,
  onToggleFullscreen,
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
        <IconButton
          label={fullscreen ? "Exit full screen" : "Full screen"}
          onClick={onToggleFullscreen}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mx-auto"
          >
            {fullscreen ? (
              <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
            ) : (
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
            )}
          </svg>
        </IconButton>
        <button
          type="button"
          aria-label="Close chat"
          title="Close chat"
          onClick={onClose}
          className="ml-1 flex h-7 w-7 items-center justify-center rounded-full bg-red-500 text-white text-xs leading-none shadow hover:bg-red-600 transition-colors"
        >
          ✕
        </button>
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
