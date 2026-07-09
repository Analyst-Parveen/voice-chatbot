"use client";

import { useCallback, useRef } from "react";

import type { ServerEvent, WidgetConfig } from "../lib/types";

/**
 * Thin client for the voice WebSocket (`/ws/voice`). Sends a recorded audio
 * Blob and forwards server events to a callback. The backend acknowledges audio
 * today and performs full STT/TTS in Phase 7 — this hook is the stable client
 * contract that Phase 7 completes end-to-end (including barge-in).
 */
export function useVoiceSocket(
  config: WidgetConfig,
  onEvent: (evt: ServerEvent) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);

  const ensure = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      const existing = wsRef.current;
      if (existing && existing.readyState === WebSocket.OPEN) {
        resolve(existing);
        return;
      }
      const ws = new WebSocket(`${config.wsBaseUrl}/ws/voice`);
      wsRef.current = ws;
      ws.binaryType = "arraybuffer";
      ws.onopen = () => resolve(ws);
      ws.onerror = () => reject(new Error("voice socket error"));
      ws.onmessage = (e) => {
        try {
          onEvent(JSON.parse(e.data) as ServerEvent);
        } catch {
          /* ignore non-JSON frames */
        }
      };
    });
  }, [config.wsBaseUrl, onEvent]);

  /** Send captured audio for transcription (processed server-side in Phase 7). */
  const sendAudio = useCallback(
    async (blob: Blob, sessionId: string | null) => {
      const ws = await ensure();
      ws.send(JSON.stringify({ type: "audio_start", session_id: sessionId }));
      ws.send(await blob.arrayBuffer());
      ws.send(JSON.stringify({ type: "audio_end" }));
    },
    [ensure],
  );

  /** Barge-in: tell the server to stop generating/speaking. */
  const interrupt = useCallback(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "interrupt" }));
    }
  }, []);

  const close = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { sendAudio, interrupt, close };
}
