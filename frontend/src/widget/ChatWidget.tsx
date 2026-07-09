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
import { VoiceAgentLogo } from "./VoiceAgentLogo";

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

/** Guidance bubble: speaks the text and reveals it word-by-word IN SYNC with
 *  the voice (via utterance word boundaries). When voice is off/unavailable it
 *  falls back to a typewriter reveal. Text never appears before it is spoken. */
function GuidanceBubble({ text, voiceOn }: { text: string; voiceOn: boolean }) {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    setShown(0);
    let typer: ReturnType<typeof setInterval> | null = null;
    const typeOut = (ms: number) => {
      if (typer) clearInterval(typer);
      typer = setInterval(
        () =>
          setShown((n) => {
            if (n >= text.length && typer) clearInterval(typer);
            return Math.min(n + 1, text.length);
          }),
        ms,
      );
    };

    const canSpeak =
      voiceOn && typeof window !== "undefined" && "speechSynthesis" in window;
    if (!canSpeak) {
      typeOut(22);
      return () => {
        if (typer) clearInterval(typer);
      };
    }

    let boundaryFired = false;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.lang = "en-IN";
    utterance.onboundary = (e) => {
      boundaryFired = true;
      // Reveal up to the end of the word being spoken right now.
      const next = text.indexOf(" ", e.charIndex + 1);
      setShown(next === -1 ? text.length : next);
    };
    utterance.onend = () => setShown(text.length);

    const start = setTimeout(() => {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
      // Some browsers never fire word boundaries — fall back to slow typing
      // roughly matching speech pace so text still follows the voice.
      setTimeout(() => {
        if (!boundaryFired) typeOut(55);
      }, 800);
    }, 350);

    return () => {
      clearTimeout(start);
      if (typer) clearInterval(typer);
      window.speechSynthesis.cancel();
    };
  }, [text, voiceOn]);

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
  const [menuOpen, setMenuOpen] = useState(false);

  // After a send, late mic transcripts must not re-fill the input bar.
  const suppressDraftRef = useRef(false);
  const applyDraft = useCallback((text: string) => {
    if (suppressDraftRef.current) return;
    setInputDraft(text);
  }, []);

  const api = useMemo(
    () => createApi(config.apiBaseUrl, config.token),
    [config.apiBaseUrl, config.token],
  );
  const chat = useChatSocket(config, {
    onInfo: setVoiceNote,
    onTranscriptDraft: applyDraft,
    muted,
  });
  const helpdesk = useHelpdesk(config.apiBaseUrl, config.token);

  const transcribeRef = useRef(chat.transcribeAudio);
  transcribeRef.current = chat.transcribeAudio;

  const mic = useWhisperMic({
    sttCode: queryLanguage?.sttCode ?? "en",
    onDraft: applyDraft,
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

  // ---- Spoken guidance: each screen shows + speaks a helper message.
  // The GuidanceBubble component speaks it and reveals the text word-by-word
  // in sync with the voice, so nothing is written before it is spoken.
  const guidanceVoiceOn = config.voiceEnabled && !muted;

  const welcome = useMemo(
    () =>
      `Namaste! Welcome to ${config.title}. I'm Ira, your AI voice assistant, ` +
      "and I'm here to help you round the clock. I can answer your questions " +
      "about our plans, coverage, claims, and services in seconds. You can " +
      "talk to me by typing, speaking, or simply picking an option below — " +
      "so, how may I help you today?",
    [config.title],
  );

  const languagePrompt =
    "Great choice! To ask a query, please select your preferred language from " +
    "the list below. You can chat with me in English or Hindi — and Hinglish " +
    "works too, just like you type on WhatsApp. Pick whichever feels most " +
    "comfortable to you.";

  const concernPrompt = useMemo(() => {
    if (!queryLanguage) return "";
    return (
      `Thank you! Now please share your concern in ${queryLanguage.label} — ` +
      "how may I help you today? Type your question, tap the mic and speak, " +
      "or pick a suggested question below. I'll search our knowledge base " +
      "and give you an accurate answer right away — please ask me something."
    );
  }, [queryLanguage]);

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
    suppressDraftRef.current = false; // fresh recording: drafts welcome again
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
      // Block late mic transcripts from re-filling the input after send.
      suppressDraftRef.current = true;
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
          aria-label="Open chat"
          className={cn(
            "va-logo-launcher fixed bottom-4 sm:bottom-6 z-[9998]",
            positionClass,
          )}
        >
          <VoiceAgentLogo />
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
                <GuidanceBubble text={welcome} voiceOn={guidanceVoiceOn} />
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
            <div className="flex flex-1 flex-col min-h-0">
              <div className="pt-3 pb-1">
                <GuidanceBubble text={languagePrompt} voiceOn={guidanceVoiceOn} />
              </div>
              <LanguageSelector
                languages={CHAT_LANGUAGES}
                onSelect={setQueryLanguage}
                onBack={backToModes}
              />
            </div>
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

                {/* Chat options: vertical menu (new / previous / language / delete) */}
                <div className="relative shrink-0">
                  <button
                    type="button"
                    onClick={() => setMenuOpen((o) => !o)}
                    aria-label="Chat options"
                    title="Chat options"
                    className={cn(
                      "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium",
                      "text-white shadow-md transition-transform hover:scale-105 active:scale-95",
                    )}
                    style={{ backgroundColor: "var(--va-accent)" }}
                  >
                    🌐 {queryLanguage.label}
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      className={cn("transition-transform", menuOpen && "rotate-180")}
                    >
                      <path d="m6 9 6 6 6-6" />
                    </svg>
                  </button>

                  {menuOpen && (
                    <>
                      {/* click-away backdrop */}
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setMenuOpen(false)}
                      />
                      <div className="absolute right-0 top-full mt-1.5 z-20 flex w-52 flex-col gap-1.5 rounded-2xl bg-white dark:bg-neutral-900 p-2 shadow-2xl border border-neutral-200 dark:border-neutral-700">
                        <button
                          type="button"
                          onClick={() => {
                            setMenuOpen(false);
                            chat.interrupt();
                            chat.newChat();
                            setInputDraft("");
                          }}
                          className="flex w-full items-center gap-2.5 rounded-xl border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/40 px-3.5 py-2.5 text-left text-xs font-semibold text-emerald-700 dark:text-emerald-300 shadow-lg hover:scale-[1.03] active:scale-[0.97] transition-transform"
                        >
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
                            ＋
                          </span>
                          New chat
                        </button>
                        <button
                          type="button"
                          disabled={!chat.hasPreviousChat}
                          onClick={() => {
                            setMenuOpen(false);
                            chat.interrupt();
                            void chat.loadPreviousChat();
                            setInputDraft("");
                          }}
                          className="flex w-full items-center gap-2.5 rounded-xl border border-sky-300 dark:border-sky-700 bg-sky-50 dark:bg-sky-900/40 px-3.5 py-2.5 text-left text-xs font-semibold text-sky-700 dark:text-sky-300 shadow-lg hover:scale-[1.03] active:scale-[0.97] transition-transform disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
                        >
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500 text-white">
                            🕘
                          </span>
                          Previous chat
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setMenuOpen(false);
                            chat.interrupt();
                            chat.newChat(); // fresh window for the new language
                            setInputDraft("");
                            setQueryLanguage(null);
                          }}
                          className="flex w-full items-center gap-2.5 rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/40 px-3.5 py-2.5 text-left text-xs font-semibold text-amber-700 dark:text-amber-300 shadow-lg hover:scale-[1.03] active:scale-[0.97] transition-transform"
                        >
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500 text-white">
                            🌐
                          </span>
                          Switch language
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setMenuOpen(false);
                            chat.interrupt();
                            void chat.clear();
                            setInputDraft("");
                          }}
                          className="flex w-full items-center gap-2.5 rounded-xl border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/40 px-3.5 py-2.5 text-left text-xs font-semibold text-red-700 dark:text-red-300 shadow-lg hover:scale-[1.03] active:scale-[0.97] transition-transform"
                        >
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500 text-white">
                            🗑
                          </span>
                          Delete chat
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
              {chat.messages.length === 0 ? (
                <div className="flex-1 overflow-y-auto">
                  <div className="pt-4 pb-2">
                    <GuidanceBubble text={concernPrompt} voiceOn={guidanceVoiceOn} />
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
