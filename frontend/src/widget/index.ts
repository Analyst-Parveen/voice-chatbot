"use client";

// Embeddable entry point. Phase 10 bundles this file into a standalone
// widget.js so any website can mount the assistant with one snippet:
//
//   <script src="https://YOUR_SERVER/widget.js" defer></script>
//   <div id="voice-ai-widget" data-api="https://YOUR_SERVER"></div>
//
// Inside the Next app, use the <ChatWidget /> component directly instead.

import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";

import { configFromElement } from "../lib/config";
import type { WidgetConfig } from "../lib/types";
import { ChatWidget } from "./ChatWidget";

export { ChatWidget } from "./ChatWidget";
export type { WidgetConfig } from "../lib/types";

const roots = new WeakMap<HTMLElement, Root>();

/** Mount the widget into a host element (by id or element). */
export function mount(
  target: string | HTMLElement,
  overrides?: Partial<WidgetConfig>,
): void {
  const el =
    typeof target === "string" ? document.getElementById(target) : target;
  if (!el) {
    console.error(`[voice-ai-widget] mount target not found: ${target}`);
    return;
  }
  const config = { ...configFromElement(el), ...(overrides ?? {}) };
  const root = roots.get(el) ?? createRoot(el);
  roots.set(el, root);
  root.render(createElement(ChatWidget, { config }));
}

/** Unmount a previously mounted widget. */
export function unmount(target: string | HTMLElement): void {
  const el =
    typeof target === "string" ? document.getElementById(target) : target;
  if (!el) return;
  roots.get(el)?.unmount();
  roots.delete(el);
}

// Auto-mount when loaded as a plain script against the default host element.
if (typeof window !== "undefined") {
  const boot = () => {
    const el = document.getElementById("voice-ai-widget");
    if (el) mount(el);
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
}
