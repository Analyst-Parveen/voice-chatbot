// Standalone embeddable entry — bundled into public/widget.js by esbuild.
//
// One-snippet embed on any website:
//   <script src="https://YOUR_SERVER/widget.js" defer></script>
//   <div id="voice-ai-widget" data-api="https://YOUR_SERVER"></div>
//
// Or mount imperatively:  VoiceAI.mount('#voice-ai-widget', { userRef, token })
//
// The widget renders inside a Shadow DOM with its own compiled CSS injected, so
// it is fully isolated from the host page's styles (and vice versa).

import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";

import { configFromElement } from "../lib/config";
import type { WidgetConfig } from "../lib/types";
import { ChatWidget } from "../widget/ChatWidget";
// esbuild inlines this compiled CSS as a string (text loader).
import cssText from "./widget.generated.css";

const roots = new Map<HTMLElement, Root>();

function resolve(target: string | HTMLElement): HTMLElement | null {
  return typeof target === "string" ? document.getElementById(target) : target;
}

export function mount(
  target: string | HTMLElement,
  overrides?: Partial<WidgetConfig>,
): void {
  const host = resolve(target);
  if (!host) {
    console.error(`[voice-ai-widget] mount target not found: ${target}`);
    return;
  }
  const shadow = host.shadowRoot ?? host.attachShadow({ mode: "open" });
  shadow.innerHTML = "";

  const style = document.createElement("style");
  style.textContent = cssText as unknown as string;
  shadow.appendChild(style);

  const container = document.createElement("div");
  shadow.appendChild(container);

  const config = { ...configFromElement(host), ...(overrides ?? {}) };
  const root = createRoot(container);
  roots.set(host, root);
  root.render(createElement(ChatWidget, { config }));
}

export function unmount(target: string | HTMLElement): void {
  const host = resolve(target);
  if (!host) return;
  roots.get(host)?.unmount();
  roots.delete(host);
}

// Auto-mount against the conventional host element when loaded as a script tag.
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
