"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface RecorderOptions {
  /** Called ~60fps with the current input level (0..1) for the wave animation. */
  onVolume?: (level: number) => void;
  /** Auto-stop after this many ms below the silence threshold. */
  silenceMs?: number;
  /** Called when recording auto-stops due to silence. */
  onAutoStop?: () => void;
}

/**
 * Microphone capture via MediaRecorder plus a lightweight Voice Activity
 * Detection loop (RMS level) driving the wave animation and silence auto-stop.
 * The recorded audio Blob is returned by stop() and handed to the voice socket
 * in Phase 7. Fully client-side and free.
 */
export function useRecorder(options: RecorderOptions = {}) {
  const { onVolume, silenceMs = 1400, onAutoStop } = options;

  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const hasSpokenRef = useRef(false);
  const stopResolveRef = useRef<((b: Blob | null) => void) | null>(null);

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
  }, []);

  const stop = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(null);
        return;
      }
      stopResolveRef.current = resolve;
      recorder.stop();
    });
  }, []);

  const monitor = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const buf = new Uint8Array(analyser.fftSize);
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buf.length);
      onVolume?.(Math.min(1, rms * 3));

      const now = performance.now();
      if (rms >= 0.02) hasSpokenRef.current = true;

      if (rms < 0.02 && hasSpokenRef.current) {
        if (silenceStartRef.current == null) silenceStartRef.current = now;
        else if (now - silenceStartRef.current > silenceMs) {
          onAutoStop?.();
          return;
        }
      } else {
        silenceStartRef.current = null;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [onVolume, onAutoStop, silenceMs]);

  const start = useCallback(async () => {
    if (!supported) {
      setError("Microphone not supported in this browser.");
      return;
    }
    try {
      setError(null);
      hasSpokenRef.current = false;
      silenceStartRef.current = null;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        cleanup();
        setIsRecording(false);
        onVolume?.(0);
        stopResolveRef.current?.(blob);
        stopResolveRef.current = null;
      };

      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyserRef.current = analyser;

      recorder.start();
      setIsRecording(true);
      monitor();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Microphone access denied.");
      cleanup();
    }
  }, [supported, cleanup, monitor, onVolume]);

  useEffect(() => cleanup, [cleanup]);

  return { isRecording, start, stop, error, supported };
}
