// REST client for the backend (suggestions, history, feedback, session).
// Streaming chat goes over WebSocket (see hooks/useChatSocket).

import type { HelpdeskStep, InputType, Role } from "./types";

async function asJson(res: Response) {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface HistoryMessage {
  id: string;
  role: Role;
  content: string;
  input_type: InputType;
  created_at: string;
  latency_ms: number | null;
}

export function createApi(baseUrl: string, token?: string) {
  const authHeaders: Record<string, string> = token
    ? { authorization: `Bearer ${token}` }
    : {};

  return {
    async getSuggestions(): Promise<string[]> {
      const data = await fetch(`${baseUrl}/api/suggestions`, {
        headers: authHeaders,
      }).then(asJson);
      return data.suggestions ?? [];
    },

    async getHistory(
      sessionId: string,
    ): Promise<{ messages: HistoryMessage[]; total: number }> {
      return fetch(`${baseUrl}/api/history/${sessionId}`, {
        headers: authHeaders,
      }).then(asJson);
    },

    async submitFeedback(
      messageId: string,
      rating: "up" | "down",
      comment?: string,
    ): Promise<void> {
      await fetch(`${baseUrl}/api/feedback`, {
        method: "POST",
        headers: { "content-type": "application/json", ...authHeaders },
        body: JSON.stringify({ message_id: messageId, rating, comment }),
      }).then(asJson);
    },

    async clearSession(sessionId: string): Promise<void> {
      await fetch(`${baseUrl}/api/session/${sessionId}`, {
        method: "DELETE",
        headers: authHeaders,
      });
    },

    async startHelpdesk(): Promise<{ session_id: string; step: HelpdeskStep }> {
      try {
        const res = await fetch(`${baseUrl}/api/helpdesk/start`, {
          method: "POST",
          headers: { "content-type": "application/json", ...authHeaders },
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(
            (data as { detail?: string }).detail ??
              `Helpdesk unavailable (HTTP ${res.status}). Is the backend running on ${baseUrl}?`,
          );
        }
        return res.json();
      } catch (e) {
        if (e instanceof TypeError) {
          throw new Error(
            `Cannot reach backend at ${baseUrl}. Start it with: python -m uvicorn app.main:app --reload --port 8000`,
          );
        }
        throw e;
      }
    },

    async respondHelpdesk(
      sessionId: string,
      answer: string,
    ): Promise<{
      session_id: string;
      completed: boolean;
      step?: HelpdeskStep;
      message?: string;
      external_ref?: string;
    }> {
      return fetch(`${baseUrl}/api/helpdesk/respond`, {
        method: "POST",
        headers: { "content-type": "application/json", ...authHeaders },
        body: JSON.stringify({ session_id: sessionId, answer }),
      }).then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
        return data;
      });
    },
  };
}

export type ApiClient = ReturnType<typeof createApi>;
