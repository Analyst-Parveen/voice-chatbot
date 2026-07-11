"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { createApi } from "../lib/api";
import { uid } from "../lib/cn";
import { getWidgetUserRef } from "../lib/widgetUser";
import type {
  ChatMessageT,
  InputType,
  ServerEvent,
  WidgetConfig,
} from "../lib/types";

const STORAGE_KEY = "voiceai_session_id";
const PREV_KEY = "voiceai_prev_session_id";

interface Options {
  /** Called with non-fatal server notes (e.g. "No speech detected"). */
  onInfo?: (message: string) => void;
  /** STT-only path: transcript for the input bar (no assistant turn). */
  onTranscriptDraft?: (text: string) => void;
  /** Current mute state — when true, spoken audio is skipped (text still shows). */
  muted?: boolean;
}

interface SayItem {
  text: string;
  audio: string;
  mime: string;
}

/**
 * Owns the chat + voice WebSockets and the shared message list.
 *
 * Spoken answers arrive as ``say`` events (sentence text + its audio). We play
 * them one at a time and reveal each sentence's text exactly when its audio
 * starts — so the on-screen text follows the voice instead of racing ahead.
 * Plain text answers (muted / text-only) still stream token-by-token.
 */
export function useChatSocket(config: WidgetConfig, options: Options = {}) {
  const [messages, setMessages] = useState<ChatMessageT[]>([]);
  const [connected, setConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [prevSessionId, setPrevSessionId] = useState<string | null>(null);
  // True while the user is viewing the swapped-in previous chat instead of the
  // one they were last actively in. Drives the "Current chat" ⇄ "Previous chat"
  // toggle in the UI. Reset whenever a fresh/cleared conversation starts.
  const [viewingPrevious, setViewingPrevious] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const voiceWsRef = useRef<WebSocket | null>(null);
  const sessionRef = useRef<string | null>(null);
  const streamingIdRef = useRef<string | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedRef = useRef(false);
  const api = useRef(createApi(config.apiBaseUrl, config.token));
  const userRefRef = useRef(getWidgetUserRef(config.userRef));

  useEffect(() => {
    userRefRef.current = getWidgetUserRef(config.userRef);
  }, [config.userRef]);

  const onInfoRef = useRef(options.onInfo);
  onInfoRef.current = options.onInfo;
  const onTranscriptDraftRef = useRef(options.onTranscriptDraft);
  onTranscriptDraftRef.current = options.onTranscriptDraft;
  const transcribeOnlyRef = useRef(false);
  const pendingTranscriptRef = useRef<{ settle: (text: string | null) => void } | null>(null);
  const mutedRef = useRef(!!options.muted);
  mutedRef.current = !!options.muted;

  // Paced spoken-answer playback.
  const sayQueueRef = useRef<SayItem[]>([]);
  const speakingRef = useRef(false);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const pendingDoneRef = useRef<ServerEvent | null>(null);
  // Voice path streams answer text via token events; say only carries audio.
  const voiceTextStreamedRef = useRef(false);

  const patch = useCallback((id: string, upd: Partial<ChatMessageT>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...upd } : m)));
  }, []);

  const appendToStreaming = useCallback((text: string) => {
    const id = streamingIdRef.current;
    if (!id) return;
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content: m.content + text } : m)),
    );
  }, []);

  const finalizeDone = useCallback(
    (evt: Extract<ServerEvent, { type: "done" }>) => {
      const id = streamingIdRef.current;
      if (id) {
        patch(id, { streaming: false, serverId: evt.message_id, sources: evt.sources });
      }
      streamingIdRef.current = null;
      voiceTextStreamedRef.current = false;
      setIsStreaming(false);
    },
    [patch],
  );

  const startAssistantTurn = useCallback(
    (userContent: string, inputType: InputType) => {
      const now = new Date().toISOString();
      const assistantId = uid();
      streamingIdRef.current = assistantId;
      voiceTextStreamedRef.current = false;
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "user", content: userContent, inputType, createdAt: now },
        {
          id: assistantId,
          role: "assistant",
          content: "",
          inputType: "text",
          createdAt: now,
          streaming: true,
        },
      ]);
      setIsStreaming(true);
    },
    [],
  );

  // Play the next queued sentence: reveal its text, then speak it; advance on end.
  const playNextSay = useCallback(() => {
    if (speakingRef.current) return;
    const item = sayQueueRef.current.shift();
    if (!item) {
      if (pendingDoneRef.current) {
        finalizeDone(pendingDoneRef.current as Extract<ServerEvent, { type: "done" }>);
        pendingDoneRef.current = null;
      }
      return;
    }
    if (!voiceTextStreamedRef.current) {
      appendToStreaming(item.text);
    }

    if (item.audio && !mutedRef.current) {
      const audio = new Audio(`data:${item.mime};base64,${item.audio}`);
      audioElRef.current = audio;
      speakingRef.current = true;
      setIsSpeaking(true);
      const advance = () => {
        speakingRef.current = false;
        setIsSpeaking(false);
        audioElRef.current = null;
        playNextSay();
      };
      audio.onended = advance;
      audio.onerror = advance;
      audio.play().catch(advance);
    } else {
      // Muted or no audio: reveal remaining text without waiting.
      playNextSay();
    }
  }, [appendToStreaming, finalizeDone]);

  const stopSpeaking = useCallback(() => {
    // Reveal any not-yet-shown text so the message stays complete.
    if (!voiceTextStreamedRef.current) {
      for (const item of sayQueueRef.current) appendToStreaming(item.text);
    }
    sayQueueRef.current = [];
    if (audioElRef.current) {
      audioElRef.current.pause();
      audioElRef.current = null;
    }
    speakingRef.current = false;
    setIsSpeaking(false);
    if (pendingDoneRef.current) {
      finalizeDone(pendingDoneRef.current as Extract<ServerEvent, { type: "done" }>);
      pendingDoneRef.current = null;
    }
  }, [appendToStreaming, finalizeDone]);

  const handleEvent = useCallback(
    (evt: ServerEvent) => {
      const streamingId = streamingIdRef.current;
      switch (evt.type) {
        case "session":
          sessionRef.current = evt.session_id;
          setSessionId(evt.session_id);
          try {
            localStorage.setItem(STORAGE_KEY, evt.session_id);
          } catch {
            /* storage may be unavailable */
          }
          break;
        case "transcript":
          if (transcribeOnlyRef.current || pendingTranscriptRef.current) {
            transcribeOnlyRef.current = false;
            onTranscriptDraftRef.current?.(evt.text);
            pendingTranscriptRef.current?.settle(evt.text);
            pendingTranscriptRef.current = null;
            break;
          }
          startAssistantTurn(evt.text, "voice");
          break;
        case "token": // text streaming (voice + text sockets)
          voiceTextStreamedRef.current = true;
          if (streamingId) appendToStreaming(evt.token);
          break;
        case "say": // spoken path: queue sentence, play when ready
          sayQueueRef.current.push({ text: evt.text, audio: evt.audio, mime: evt.mime });
          playNextSay();
          break;
        case "done":
          if (sayQueueRef.current.length > 0 || speakingRef.current) {
            pendingDoneRef.current = evt; // finalize after speech finishes
          } else {
            finalizeDone(evt);
          }
          break;
        case "error":
          if (pendingTranscriptRef.current) {
            pendingTranscriptRef.current.settle(null);
            pendingTranscriptRef.current = null;
            transcribeOnlyRef.current = false;
          }
          if (streamingId) {
            patch(streamingId, { streaming: false, error: true, content: `⚠️ ${evt.message}` });
          }
          stopSpeaking();
          streamingIdRef.current = null;
          setIsStreaming(false);
          break;
        case "info":
          if (
            pendingTranscriptRef.current &&
            /no speech detected/i.test(evt.message)
          ) {
            pendingTranscriptRef.current.settle(null);
            pendingTranscriptRef.current = null;
            transcribeOnlyRef.current = false;
          }
          onInfoRef.current?.(evt.message);
          break;
      }
    },
    [appendToStreaming, finalizeDone, patch, playNextSay, startAssistantTurn, stopSpeaking],
  );

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return;
    const ws = new WebSocket(`${config.wsBaseUrl}/ws/chat`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      if (!closedRef.current) reconnectRef.current = setTimeout(connect, 1500);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      try {
        handleEvent(JSON.parse(e.data) as ServerEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
  }, [config.wsBaseUrl, handleEvent]);

  const connectVoice = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      const existing = voiceWsRef.current;
      if (existing && existing.readyState === WebSocket.OPEN) {
        resolve(existing);
        return;
      }
      const ws = new WebSocket(`${config.wsBaseUrl}/ws/voice`);
      voiceWsRef.current = ws;
      ws.binaryType = "arraybuffer";
      ws.onopen = () => resolve(ws);
      ws.onerror = () => reject(new Error("voice socket error"));
      ws.onmessage = (e) => {
        try {
          handleEvent(JSON.parse(e.data) as ServerEvent);
        } catch {
          /* ignore non-JSON frames */
        }
      };
    });
  }, [config.wsBaseUrl, handleEvent]);

  // Connect chat socket on mount; restore session + history.
  useEffect(() => {
    closedRef.current = false;
    connect();

    let stored: string | null = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY);
      setPrevSessionId(localStorage.getItem(PREV_KEY));
    } catch {
      stored = null;
    }
    if (stored) {
      sessionRef.current = stored;
      setSessionId(stored);
      api.current
        .getHistory(stored)
        .then((h) => {
          if (h.messages?.length) {
            setMessages(
              h.messages.map((m) => ({
                id: m.id,
                serverId: m.id,
                role: m.role,
                content: m.content,
                inputType: m.input_type,
                createdAt: m.created_at,
              })),
            );
          }
        })
        .catch(() => {
          /* stale session — start fresh */
        });
    }

    return () => {
      closedRef.current = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
      voiceWsRef.current?.close();
    };
  }, [connect]);

  const sendText = useCallback(
    (text: string, inputType: InputType = "text", speak = false, language?: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      startAssistantTurn(trimmed, inputType);
      const payload = JSON.stringify({
        type: "message",
        session_id: sessionRef.current,
        message: trimmed,
        input_type: inputType,
        user_ref: userRefRef.current,
        ...(language ? { language } : {}),
      });

      const failTurn = () => {
        const id = streamingIdRef.current;
        if (id) {
          patch(id, {
            streaming: false,
            error: true,
            content: "⚠️ Could not reach the assistant. Please try again.",
          });
        }
        streamingIdRef.current = null;
        setIsStreaming(false);
      };

      // "speak" → voice socket (server also synthesizes speech). Else text socket.
      if (speak) {
        connectVoice()
          .then((ws) => ws.send(payload))
          .catch(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(payload);
            } else {
              failTurn();
            }
          });
        return;
      }

      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(payload);
      } else {
        connect();
        const trySend = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(payload);
            clearInterval(trySend);
          }
        }, 200);
        setTimeout(() => clearInterval(trySend), 5000);
      }
    },
    [connect, connectVoice, isStreaming, patch, startAssistantTurn],
  );

  const transcribeAudio = useCallback(
    async (blob: Blob, sttCode?: string): Promise<string | null> => {
      if (isStreaming) return null;
      return new Promise<string | null>((resolve) => {
        const timeout = window.setTimeout(() => {
          if (pendingTranscriptRef.current) {
            pendingTranscriptRef.current.settle(null);
            pendingTranscriptRef.current = null;
            transcribeOnlyRef.current = false;
          }
        }, 45000);

        const pending = {
          settle: (text: string | null) => {
            window.clearTimeout(timeout);
            resolve(text);
          },
        };
        pendingTranscriptRef.current = pending;
        transcribeOnlyRef.current = true;

        connectVoice()
          .then(async (ws) => {
            ws.send(
              JSON.stringify({
                type: "audio_start",
                session_id: sessionRef.current,
                user_ref: userRefRef.current,
                transcribe_only: true,
                ...(sttCode ? { stt_language: sttCode } : {}),
              }),
            );
            ws.send(await blob.arrayBuffer());
            ws.send(JSON.stringify({ type: "audio_end" }));
          })
          .catch(() => {
            window.clearTimeout(timeout);
            transcribeOnlyRef.current = false;
            pendingTranscriptRef.current = null;
            onInfoRef.current?.("Voice service unavailable.");
            resolve(null);
          });
      });
    },
    [connectVoice, isStreaming],
  );

  const sendAudio = useCallback(
    async (blob: Blob, language?: string) => {
      if (isStreaming) return;
      try {
        const ws = await connectVoice();
        ws.send(
          JSON.stringify({
            type: "audio_start",
            session_id: sessionRef.current,
            user_ref: userRefRef.current,
            ...(language ? { language } : {}),
          }),
        );
        ws.send(await blob.arrayBuffer());
        ws.send(JSON.stringify({ type: "audio_end" }));
      } catch {
        onInfoRef.current?.("Voice service unavailable.");
      }
    },
    [connectVoice, isStreaming],
  );

  const interrupt = useCallback(() => {
    const vws = voiceWsRef.current;
    if (vws && vws.readyState === WebSocket.OPEN) {
      vws.send(JSON.stringify({ type: "interrupt" }));
    }
    stopSpeaking();
    const id = streamingIdRef.current;
    if (id) patch(id, { streaming: false });
    streamingIdRef.current = null;
    setIsStreaming(false);
  }, [patch, stopSpeaking]);

  /** Reset local chat state. When `savePrev` the departing session id is
   *  remembered so `loadPreviousChat` can bring it back. */
  const resetLocal = useCallback(
    (savePrev: boolean) => {
      const departing = sessionRef.current;
      stopSpeaking();
      setMessages([]);
      streamingIdRef.current = null;
      setIsStreaming(false);
      sessionRef.current = null;
      setSessionId(null);
      setViewingPrevious(false);
      try {
        localStorage.removeItem(STORAGE_KEY);
        if (savePrev && departing) {
          localStorage.setItem(PREV_KEY, departing);
          setPrevSessionId(departing);
        }
      } catch {
        /* ignore */
      }
    },
    [stopSpeaking],
  );

  /** Start a fresh conversation locally (new session on next message).
   *  Unlike `clear`, the previous session's history stays on the server. */
  const newChat = useCallback(() => resetLocal(true), [resetLocal]);

  const clear = useCallback(async () => {
    const current = sessionRef.current;
    resetLocal(false); // deleted server-side — don't offer it as "previous"
    if (current) {
      try {
        await api.current.clearSession(current);
      } catch {
        /* best effort */
      }
    }
  }, [resetLocal]);

  /** Swap back to the remembered previous session (history reloads from the
   *  server). The current session becomes the new "previous", so the button
   *  toggles between the two most recent chats. */
  const loadPreviousChat = useCallback(async (): Promise<boolean> => {
    const prev = prevSessionId;
    if (!prev) return false;
    try {
      const h = await api.current.getHistory(prev);
      const current = sessionRef.current;
      stopSpeaking();
      streamingIdRef.current = null;
      setIsStreaming(false);
      sessionRef.current = prev;
      setSessionId(prev);
      try {
        localStorage.setItem(STORAGE_KEY, prev);
        if (current) {
          localStorage.setItem(PREV_KEY, current);
          setPrevSessionId(current);
        } else {
          localStorage.removeItem(PREV_KEY);
          setPrevSessionId(null);
        }
      } catch {
        /* ignore */
      }
      setMessages(
        (h.messages ?? []).map((m) => ({
          id: m.id,
          serverId: m.id,
          role: m.role,
          content: m.content,
          inputType: m.input_type,
          createdAt: m.created_at,
        })),
      );
      // Each swap flips which of the two chats is on screen, so the toggle
      // label switches between "Previous chat" and "Current chat".
      setViewingPrevious((v) => !v);
      return true;
    } catch {
      onInfoRef.current?.("Previous chat is unavailable.");
      return false;
    }
  }, [prevSessionId, stopSpeaking]);

  return {
    messages,
    connected,
    isStreaming,
    isSpeaking,
    sessionId,
    sendText,
    sendAudio,
    transcribeAudio,
    interrupt,
    stopSpeaking,
    clear,
    newChat,
    loadPreviousChat,
    hasPreviousChat: prevSessionId !== null,
    viewingPrevious,
  };
}
