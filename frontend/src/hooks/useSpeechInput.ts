"use client";

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";

type SpeechRecognitionCtor = new () => SpeechRecognition;

function getSpeechRecognition(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

interface Options {
  onInterim?: (text: string) => void;
  onFinal?: (text: string) => void;
  /** BCP-47 tag(s), e.g. "hi-IN,en-IN". */
  lang?: string;
  /** True while the mic session is active — keeps recognition alive across browser restarts. */
  activeRef?: MutableRefObject<boolean>;
}

/**
 * Browser speech-to-text for live transcript in the input bar while the mic
 * is active. Falls back gracefully when unsupported (server STT still works).
 */
export function useSpeechInput(options: Options = {}) {
  const [isListening, setIsListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const recRef = useRef<SpeechRecognition | null>(null);
  const finalRef = useRef("");
  const onInterimRef = useRef(options.onInterim);
  const onFinalRef = useRef(options.onFinal);
  const langRef = useRef(options.lang ?? "en-IN,en-US");
  const activeRef = options.activeRef;
  onInterimRef.current = options.onInterim;
  onFinalRef.current = options.onFinal;
  langRef.current = options.lang ?? "en-IN,en-US";

  useEffect(() => {
    setSupported(!!getSpeechRecognition());
  }, []);

  const beginRecognitionRef = useRef<() => boolean>(() => false);

  const beginRecognition = useCallback((): boolean => {
    const Ctor = getSpeechRecognition();
    if (!Ctor || !activeRef?.current) return false;

    try {
      recRef.current?.stop();
    } catch {
      /* ignore */
    }

    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = langRef.current;

    rec.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalRef.current += (finalRef.current && !finalRef.current.endsWith(" ") ? " " : "") + t;
        } else {
          interim += t;
        }
      }
      const combined = (finalRef.current + interim).trim();
      if (combined) onInterimRef.current?.(combined);
      if (finalRef.current.trim()) onFinalRef.current?.(finalRef.current.trim());
    };

    rec.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (
        activeRef?.current &&
        (event.error === "no-speech" || event.error === "aborted" || event.error === "network")
      ) {
        return;
      }
      if (activeRef) activeRef.current = false;
      try {
        recRef.current?.stop();
      } catch {
        /* ignore */
      }
      recRef.current = null;
      setIsListening(false);
    };

    rec.onend = () => {
      const text = finalRef.current.trim();
      if (text) {
        onInterimRef.current?.(text);
        onFinalRef.current?.(text);
      }
      if (activeRef?.current) {
        window.setTimeout(() => {
          if (activeRef?.current) beginRecognitionRef.current();
        }, 120);
        return;
      }
      setIsListening(false);
      recRef.current = null;
    };

    recRef.current = rec;
    rec.start();
    setIsListening(true);
    return true;
  }, [activeRef]);

  beginRecognitionRef.current = beginRecognition;

  const stop = useCallback(() => {
    if (activeRef) activeRef.current = false;
    try {
      recRef.current?.stop();
    } catch {
      /* ignore */
    }
    recRef.current = null;
    setIsListening(false);
  }, [activeRef]);

  const start = useCallback(() => {
    const Ctor = getSpeechRecognition();
    if (!Ctor) return false;
    if (activeRef) activeRef.current = true;
    finalRef.current = "";
    return beginRecognition();
  }, [activeRef, beginRecognition]);

  useEffect(() => () => stop(), [stop]);

  return { supported, isListening, start, stop };
};
