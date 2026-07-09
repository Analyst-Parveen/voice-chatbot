"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TIMESLICE_MS = 2500;
const MIN_PARTIAL_BYTES = 8000;

interface Options {
  /** Whisper ISO-639-1 code: "hi" | "en". */
  sttCode: string;
  onDraft: (text: string) => void;
  onStatus?: (message: string | null) => void;
  /** Server Whisper transcription (free, local). */
  transcribe: (blob: Blob, sttCode: string) => Promise<string | null>;
  silenceMs?: number;
}

/**
 * Mic capture with live + final transcription via server Whisper (faster-whisper).
 * Free, runs locally, works for Hindi and English without browser speech API.
 */
export function useWhisperMic({
  sttCode,
  onDraft,
  onStatus,
  transcribe,
  silenceMs = 2800,
}: Options) {
  const [isRecording, setIsRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const activeRef = useRef(false);
  const chunksRef = useRef<Blob[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const hasSpokenRef = useRef(false);
  const transcribingRef = useRef(false);
  const stopResolveRef = useRef<(() => void) | null>(null);
  const sttCodeRef = useRef(sttCode);
  const onDraftRef = useRef(onDraft);
  const onStatusRef = useRef(onStatus);
  const transcribeRef = useRef(transcribe);
  sttCodeRef.current = sttCode;
  onDraftRef.current = onDraft;
  onStatusRef.current = onStatus;
  transcribeRef.current = transcribe;

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined";

  const cleanup = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    silenceStartRef.current = null;
    analyserRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const getBlob = useCallback((): Blob | null => {
    if (chunksRef.current.length === 0) return null;
    const mime = recorderRef.current?.mimeType || "audio/webm";
    return new Blob(chunksRef.current, { type: mime });
  }, []);

  const runPartialTranscribe = useCallback(async () => {
    if (!activeRef.current || transcribingRef.current) return;
    const blob = getBlob();
    if (!blob || blob.size < MIN_PARTIAL_BYTES || !hasSpokenRef.current) return;

    transcribingRef.current = true;
    try {
      const text = await transcribeRef.current(blob, sttCodeRef.current);
      if (text && activeRef.current) onDraftRef.current(text);
    } finally {
      transcribingRef.current = false;
    }
  }, [getBlob]);

  const stopInternalRef = useRef<() => Promise<void>>(async () => {});

  const monitor = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const buf = new Uint8Array(analyser.fftSize);
    const tick = () => {
      if (!activeRef.current) return;
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buf.length);
      setLevel(Math.min(1, rms * 3));

      const now = performance.now();
      if (rms >= 0.012) hasSpokenRef.current = true;

      if (rms < 0.012 && hasSpokenRef.current) {
        if (silenceStartRef.current == null) silenceStartRef.current = now;
        else if (now - silenceStartRef.current > silenceMs) {
          void stopInternalRef.current();
          return;
        }
      } else {
        silenceStartRef.current = null;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [silenceMs]);

  stopInternalRef.current = async () => {
    if (!activeRef.current) return;
    activeRef.current = false;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;

    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      try {
        if (recorder.state === "recording") recorder.requestData();
      } catch {
        /* ignore */
      }
      await new Promise<void>((resolve) => {
        stopResolveRef.current = resolve;
        recorder.stop();
      });
    }

    while (transcribingRef.current) {
      await new Promise((r) => setTimeout(r, 80));
    }

    const blob = getBlob();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setIsRecording(false);
    setLevel(0);

    if (blob && blob.size >= MIN_PARTIAL_BYTES && hasSpokenRef.current) {
      onStatusRef.current?.("Transcribing…");
      try {
        const text = await transcribeRef.current(blob, sttCodeRef.current);
        if (text) onDraftRef.current(text);
        else {
          onStatusRef.current?.("No speech detected — try again.");
          window.setTimeout(() => onStatusRef.current?.(null), 3000);
        }
      } finally {
        onStatusRef.current?.(null);
      }
    } else if (hasSpokenRef.current) {
      onStatusRef.current?.("No speech detected — try again.");
      window.setTimeout(() => onStatusRef.current?.(null), 3000);
    } else {
      onStatusRef.current?.(null);
    }

    cleanup();
  };

  const stop = useCallback(async () => {
    await stopInternalRef.current();
  }, []);

  const start = useCallback(async () => {
    if (!supported) {
      setError("Microphone not supported in this browser.");
      return;
    }
    try {
      setError(null);
      hasSpokenRef.current = false;
      silenceStartRef.current = null;
      chunksRef.current = [];
      activeRef.current = true;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
        if (activeRef.current && hasSpokenRef.current) void runPartialTranscribe();
      };

      recorder.onstop = () => {
        stopResolveRef.current?.();
        stopResolveRef.current = null;
      };

      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyserRef.current = analyser;

      recorder.start(TIMESLICE_MS);
      setIsRecording(true);
      onStatusRef.current?.("Listening… speak now");
      monitor();
    } catch (e) {
      activeRef.current = false;
      setError(e instanceof Error ? e.message : "Microphone access denied.");
      cleanup();
      setIsRecording(false);
    }
  }, [supported, cleanup, monitor, runPartialTranscribe]);

  useEffect(() => () => {
    activeRef.current = false;
    cleanup();
  }, [cleanup]);

  return { isRecording, level, error, supported, start, stop };
};
