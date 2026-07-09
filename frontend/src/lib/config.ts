import type { WidgetConfig } from "./types";

/** Baseline config; env vars provide sensible dev defaults. */
export const DEFAULT_CONFIG: WidgetConfig = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  wsBaseUrl: process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000",
  title: "AI Assistant",
  subtitle: "Ask me anything",
  accent: "#4f46e5",
  position: "bottom-right",
  theme: "auto",
  voiceEnabled: true,
};

export function resolveConfig(overrides?: Partial<WidgetConfig>): WidgetConfig {
  return { ...DEFAULT_CONFIG, ...(overrides ?? {}) };
}

/** Read config from a host element's data-* attributes (used by mount()). */
export function configFromElement(el: HTMLElement): Partial<WidgetConfig> {
  const d = el.dataset;
  const cfg: Partial<WidgetConfig> = {};
  if (d.api) cfg.apiBaseUrl = d.api;
  if (d.ws) cfg.wsBaseUrl = d.ws;
  else if (d.api) cfg.wsBaseUrl = d.api.replace(/^http/, "ws");
  if (d.title) cfg.title = d.title;
  if (d.subtitle) cfg.subtitle = d.subtitle;
  if (d.accent) cfg.accent = d.accent;
  if (d.position === "bottom-left" || d.position === "bottom-right")
    cfg.position = d.position;
  if (d.theme === "light" || d.theme === "dark" || d.theme === "auto")
    cfg.theme = d.theme;
  if (d.voice) cfg.voiceEnabled = d.voice !== "false";
  if (d.token) cfg.token = d.token;
  if (d.userRef) cfg.userRef = d.userRef;
  return cfg;
}
