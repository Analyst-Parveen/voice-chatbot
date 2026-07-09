// Shared types for the widget. Kept framework-agnostic so the widget can be
// bundled and embedded into any site (Phase 10).

export type Role = "user" | "assistant" | "system";
export type InputType = "text" | "voice";
export type ThemeMode = "light" | "dark" | "auto";

export interface Source {
  chunk_id: string;
  source: string;
  score: number;
}

export interface ChatMessageT {
  id: string;
  role: Role;
  content: string;
  inputType: InputType;
  createdAt: string;
  streaming?: boolean;
  error?: boolean;
  sources?: Source[];
  /** Server-assigned message id (available after "done"); used for feedback. */
  serverId?: string;
}

/** Runtime configuration for the widget (also settable via data-* attrs). */
export interface WidgetConfig {
  apiBaseUrl: string;
  wsBaseUrl: string;
  title: string;
  subtitle: string;
  accent: string;
  position: "bottom-right" | "bottom-left";
  theme: ThemeMode;
  voiceEnabled: boolean;
  /** Optional JWT for authenticated REST calls (Authorization: Bearer). */
  token?: string;
  /** Host-site user id to attribute conversations to (soft handoff). */
  userRef?: string;
}

export type WidgetMode = "helpdesk" | "query" | null;

export interface HelpdeskOption {
  id: string;
  label: string;
}

export interface HelpdeskStep {
  step_id: string;
  message: string;
  field_type: "choice" | "text" | "phone" | "email" | "number" | "date" | "textarea";
  options: HelpdeskOption[];
  placeholder?: string | null;
  required?: boolean;
  progress: number;
}

export interface HelpdeskTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatLanguage {
  id: string;
  label: string;
  nativeLabel: string;
  /** Whisper ISO-639-1 code for speech recognition. */
  sttCode: string;
  replyLanguage: string;
}

// ---- WebSocket protocol (mirrors backend app/api/ws/chat_ws.py) ----

export type ServerEvent =
  | { type: "session"; session_id: string }
  | { type: "transcript"; text: string }
  | { type: "token"; token: string }
  // A sentence's text paired with its spoken audio (revealed together).
  | { type: "say"; seq: number; text: string; audio: string; mime: string }
  | { type: "done"; message_id: string; latency_ms: number; sources: Source[] }
  | { type: "error"; code: string; message: string }
  | { type: "info"; message: string };

export interface ClientMessage {
  type: "message";
  session_id: string | null;
  message: string;
  input_type: InputType;
  language?: string;
}
