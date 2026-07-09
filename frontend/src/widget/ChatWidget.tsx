"use client";

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useChatSocket } from "../hooks/useChatSocket";
import { useHelpdesk } from "../hooks/useHelpdesk";
import { useWhisperMic } from "../hooks/useWhisperMic";
import { createApi } from "../lib/api";
import { cn } from "../lib/cn";
import { CHAT_LANGUAGES } from "../lib/languages";
import { resolveConfig } from "../lib/config";
import type { ChatLanguage, ChatMessageT, WidgetConfig, WidgetMode } from "../lib/types";
import { ChatHeader } from "./ChatHeader";
import { ChatInput } from "./ChatInput";
import { HelpdeskPanel } from "./HelpdeskPanel";
import { LanguageSelector } from "./LanguageSelector";
import { MessageList } from "./MessageList";
import { ModeSelector } from "./ModeSelector";
import { SuggestedQuestions } from "./SuggestedQuestions";

/** Public entry component. Self-contained: brings its own React Query client. */
export function ChatWidget({ config: partial }: { config?: Partial<WidgetConfig> }) {
  const config = useMemo(() => resolveConfig(partial), [partial]);
  const [qc] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={qc}>
      <WidgetShell config={config} />
    </QueryClientProvider>
  );
}

/** Welcome line typed out character-by-character (also spoken on open). */
function WelcomeIntro({ text }: { text: string }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    setShown(0);
    const t = setInterval(
      () => setShown((n) => (n >= text.length ? (clearInterval(t), n) : n + 1)),
      22,
    );
    return () => clearInterval(t);
  }, [text]);
  return (
    <div className="mx-4 rounded-2xl rounded-bl-sm bg-neutral-100 dark:bg-neutral-800 px-3.5 py-3 text-sm leading-relaxed">
      {text.slice(0, shown)}
      {shown < text.length && <span className="va-caret" />}
    </div>
  );
}

function WidgetShell({ config }: { config: WidgetConfig }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<WidgetMode>(null);
  const [queryLanguage, setQueryLanguage] = useState<ChatLanguage | null>(null);
  const [inputDraft, setInputDraft] = useState("");
  const [voiceNote, setVoiceNote] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  const api = useMemo(
    () => createApi(config.apiBaseUrl, config.token),
    [config.apiBaseUrl, config.token],
  );
  const chat = useChatSocket(config, {
    onInfo: setVoiceNote,
    onTranscriptDraft: setInputDraft,
    muted,
  });
  const helpdesk = useHelpdesk(config.apiBaseUrl, config.token);

  const transcribeRef = useRef(chat.transcribeAudio);
  transcribeRef.current = chat.transcribeAudio;

  const mic = useWhisperMic({
    sttCode: queryLanguage?.sttCode ?? "en",
    onDraft: setInputDraft,
    onStatus: setVoiceNote,
    transcribe: (blob, code) => transcribeRef.current(blob, code),
  });

  // ---- Theme resolution ----
  const [override, setOverride] = useState<"light" | "dark" | null>(null);
  const [systemDark, setSystemDark] = useState(false);
  useEffect(() => {
    if (config.theme !== "auto") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setSystemDark(mq.matches);
    const handler = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [config.theme]);
  const base = config.theme === "auto" ? (systemDark ? "dark" : "light") : config.theme;
  const effectiveTheme = override ?? base;

  // ---- Welcome: typed + spoken when the widget opens ----
  const welcome = useMemo(
    () =>
      `Namaste! Welcome to ${config.title}. I'm your AI voice assistant — ` +
      "ask me anything by typing, speaking, or picking an option below.",
    [config.title],
  );

  useEffect(() => {
    if (!open || mode !== null) return;
    if (muted || !config.voiceEnabled) return;
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(welcome);
    utterance.rate = 1;
    utterance.lang = "en-IN";
    // Small delay so the open animation settles first.
    const t = setTimeout(() => window.speechSynthesis.speak(utterance), 350);
    return () => {
      clearTimeout(t);
      window.speechSynthesis.cancel();
    };
  }, [open, mode, muted, config.voiceEnabled, welcome]);

  // ---- Escape key closes the widget ----
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // ---- Voice: Whisper STT (free, local, Hindi + English) ----
  const startRecording = useCallback(async () => {
    if (!queryLanguage) return;
    setInputDraft("");
    chat.interrupt();
    await mic.start();
  }, [chat, mic, queryLanguage]);

  const stopRecording = useCallback(async () => {
    await mic.stop();
  }, [mic]);

  const handleSend = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      if (mic.isRecording) void mic.stop();
      setInputDraft("");
      chat.sendText(
        trimmed,
        "text",
        config.voiceEnabled && !muted,
        queryLanguage?.replyLanguage,
      );
    },
    [chat, config.voiceEnabled, muted, queryLanguage?.replyLanguage, mic],
  );

  useEffect(() => {
    if (!voiceNote) return;
    const t = setTimeout(() => setVoiceNote(null), 5000);
    return () => clearTimeout(t);
  }, [voiceNote]);

  const selectMode = useCallback(
    (m: "helpdesk" | "query") => {
      setMode(m);
      setQueryLanguage(null);
      if (m === "helpdesk") void helpdesk.start();
    },
    [helpdesk],
  );

  const backToModes = useCallback(() => {
    setMode(null);
    setQueryLanguage(null);
    helpdesk.reset();
    setInputDraft("");
  }, [helpdesk]);

  // ---- Suggestions ----
  const { data: suggestions = [] } = useQuery({
    queryKey: ["suggestions", config.apiBaseUrl],
    queryFn: api.getSuggestions,
    staleTime: 5 * 60 * 1000,
    enabled: mode === "query",
  });

  const onFeedback = useCallback(
    (m: ChatMessageT, rating: "up" | "down") => {
      if (m.serverId) void api.submitFeedback(m.serverId, rating);
    },
    [api],
  );

  const positionClass =
    config.position === "bottom-left" ? "left-4 sm:left-6" : "right-4 sm:right-6";

  const subtitle =
    mode === "helpdesk"
      ? "Helpdesk wizard"
      : mode === "query"
        ? queryLanguage
          ? `${config.subtitle} · ${queryLanguage.label}`
          : "Choose your language"
        : "Helpdesk · or · Ask a Query";

  return (
    <div
      className={cn(effectiveTheme === "dark" && "dark")}
      style={{ ["--va-accent" as string]: config.accent }}
    >
      {!open && (
        <button
          type="button"
          onClick={() => {
            setMode(null);
            setQueryLanguage(null);
            setInputDraft("");
            setOpen(true);
          }}
          aria-label="Open chat — click to talk"
          className={cn(
            "va-talk-launcher fixed bottom-4 sm:bottom-6 z-[9998]",
            positionClass,
          )}
        >
          <span className="va-eq" aria-hidden>
            <span className="va-eq-bar" />
            <span className="va-eq-bar" />
            <span className="va-eq-bar" />
            <span className="va-eq-bar" />
            <span className="va-eq-bar" />
            <span className="va-eq-bar" />
          </span>
          Click to Talk
        </button>
      )}

      {open && (
        <div
          className={cn(
            "fixed z-[9999] flex flex-col overflow-hidden rounded-2xl shadow-2xl",
            "bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100",
            "border border-neutral-200 dark:border-neutral-800",
            fullscreen
              ? "inset-2 sm:inset-6 w-auto h-auto"
              : cn(
                  "bottom-4 sm:bottom-6 w-[calc(100vw-2rem)] sm:w-[380px] h-[70vh] sm:h-[600px] max-h-[calc(100vh-2rem)]",
                  positionClass,
                ),
          )}
        >
          <ChatHeader
            title={config.title}
            subtitle={subtitle}
            connected={chat.connected}
            voiceEnabled={mode === "query" && config.voiceEnabled}
            muted={muted}
            effectiveTheme={effectiveTheme}
            fullscreen={fullscreen}
            onToggleFullscreen={() => setFullscreen((f) => !f)}
            onToggleMute={() => {
              const next = !muted;
              setMuted(next);
              if (next) chat.stopSpeaking();
            }}
            onToggleTheme={() =>
              setOverride(effectiveTheme === "dark" ? "light" : "dark")
            }
            onClear={() => {
              if (mode === "query") void chat.clear();
              else helpdesk.reset();
              setMode(null);
              setQueryLanguage(null);
              setInputDraft("");
            }}
            onClose={() => setOpen(false)}
          />

          {mode === null && (
            <div className="flex flex-1 flex-col min-h-0">
              <div className="pt-4 pb-2">
                <WelcomeIntro text={welcome} />
              </div>
              <ModeSelector onSelect={selectMode} />
            </div>
          )}

          {mode === "helpdesk" && (
            <HelpdeskPanel
              step={helpdesk.step}
              turns={helpdesk.turns}
              loading={helpdesk.loading}
              completed={helpdesk.completed}
              error={helpdesk.error}
              onRespond={helpdesk.respond}
              onBack={backToModes}
            />
          )}

          {mode === "query" && !queryLanguage && (
            <LanguageSelector
              languages={CHAT_LANGUAGES}
              onSelect={setQueryLanguage}
              onBack={backToModes}
            />
          )}

          {mode === "query" && queryLanguage && (
            <>
              <div className="px-4 pt-2 flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={backToModes}
                  className="text-xs text-neutral-500 hover:text-[var(--va-accent)] transition-colors"
                >
                  ← Switch to Helpdesk / Ask a Query
                </button>
                <button
                  type="button"
                  onClick={() => setQueryLanguage(null)}
                  className="text-xs text-neutral-500 hover:text-[var(--va-accent)] transition-colors shrink-0"
                >
                  {queryLanguage.nativeLabel} · Change
                </button>
              </div>
              {chat.messages.length > 0 && (
                <div className="px-4 pt-1.5 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      chat.interrupt();
                      chat.newChat();
                      setInputDraft("");
                    }}
                    title="Start a new chat (keeps this one in history)"
                    className="flex items-center gap-1 text-xs text-neutral-500 hover:text-[var(--va-accent)] transition-colors"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 5v14M5 12h14" />
                    </svg>
                    New chat
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      chat.interrupt();
                      void chat.clear();
                      setInputDraft("");
                    }}
                    title="Delete this chat permanently"
                    className="flex items-center gap-1 text-xs text-neutral-500 hover:text-red-500 transition-colors"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                    </svg>
                    Delete
                  </button>
                </div>
              )}
              {chat.messages.length === 0 ? (
                <div className="flex-1 overflow-y-auto">
                  <div className="px-4 py-6 text-sm text-neutral-500">
                    👋 Ask me anything — type, speak, or pick a suggestion below.
                  </div>
                  <SuggestedQuestions
                    suggestions={suggestions}
                    onSelect={(q) => handleSend(q)}
                  />
                </div>
              ) : (
                <MessageList messages={chat.messages} onFeedback={onFeedback} />
              )}

              {voiceNote && (
                <div className="px-4 py-1.5 text-xs text-center text-neutral-500 bg-neutral-50 dark:bg-neutral-800/50">
                  {voiceNote}
                </div>
              )}
              {mic.error && (
                <div className="px-4 py-1.5 text-xs text-center text-red-500">
                  {mic.error}
                </div>
              )}

              <ChatInput
                value={inputDraft}
                onChange={setInputDraft}
                onSend={handleSend}
                disabled={chat.isStreaming}
                isListening={mic.isRecording}
                streaming={chat.isStreaming || chat.isSpeaking}
                onStopStreaming={() => chat.interrupt()}
                voiceEnabled={config.voiceEnabled}
                voice={{
                  isRecording: mic.isRecording,
                  level: mic.level,
                  supported: mic.supported,
                  onStart: () => void startRecording(),
                  onStop: () => void stopRecording(),
                }}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}
