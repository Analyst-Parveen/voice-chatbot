"use client";

import { useCallback, useState } from "react";

import { createApi } from "../lib/api";
import type { HelpdeskStep, HelpdeskTurn } from "../lib/types";

export function useHelpdesk(apiBaseUrl: string, token?: string) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [step, setStep] = useState<HelpdeskStep | null>(null);
  const [turns, setTurns] = useState<HelpdeskTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const api = createApi(apiBaseUrl, token);

  const start = useCallback(async () => {
    setLoading(true);
    setError(null);
    setCompleted(false);
    setTurns([]);
    try {
      const res = await api.startHelpdesk();
      setSessionId(res.session_id);
      setStep(res.step);
      setTurns([{ role: "assistant", content: res.step.message }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start helpdesk");
    } finally {
      setLoading(false);
    }
  }, [api]);

  const respond = useCallback(
    async (answer: string, displayLabel?: string) => {
      if (!sessionId || !step || loading) return;
      const trimmed = answer.trim();
      if (!trimmed) return;

      setLoading(true);
      setError(null);
      setTurns((prev) => [...prev, { role: "user", content: displayLabel ?? trimmed }]);

      try {
        const res = await api.respondHelpdesk(sessionId, trimmed);
        if (res.completed) {
          setCompleted(true);
          setStep(null);
          setTurns((prev) => [
            ...prev,
            {
              role: "assistant",
              content: res.message ?? "Your request has been submitted.",
            },
          ]);
        } else if (res.step) {
          setStep(res.step);
          setTurns((prev) => [...prev, { role: "assistant", content: res.step!.message }]);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Submission failed";
        setError(msg);
        setTurns((prev) => prev.slice(0, -1));
      } finally {
        setLoading(false);
      }
    },
    [api, loading, sessionId, step],
  );

  const reset = useCallback(() => {
    setSessionId(null);
    setStep(null);
    setTurns([]);
    setCompleted(false);
    setError(null);
  }, []);

  return {
    sessionId,
    step,
    turns,
    loading,
    completed,
    error,
    start,
    respond,
    reset,
  };
}
