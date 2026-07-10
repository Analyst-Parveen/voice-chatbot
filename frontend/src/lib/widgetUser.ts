/** Stable anonymous id for this browser/widget install (persisted in localStorage). */
const STORAGE_KEY = "voiceai_widget_user_ref";

export function getWidgetUserRef(explicit?: string): string {
  const trimmed = explicit?.trim();
  if (trimmed) return trimmed;

  if (typeof window === "undefined") return "anonymous";

  let ref = localStorage.getItem(STORAGE_KEY);
  if (!ref) {
    ref =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? `widget-${crypto.randomUUID()}`
        : `widget-${Date.now()}`;
    localStorage.setItem(STORAGE_KEY, ref);
  }
  return ref;
}
