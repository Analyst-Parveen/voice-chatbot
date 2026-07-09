"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Sequential audio playback for TTS chunks streamed from the server (Phase 7).
 * Accepts base64-encoded audio, queues it, and plays clips in order. Supports
 * mute and stop-speaking (barge-in). Interface is ready now; the server starts
 * sending audio in Phase 7.
 */
export function useAudioPlayer() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);

  const queueRef = useRef<string[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mutedRef = useRef(false);

  useEffect(() => {
    mutedRef.current = muted;
    if (muted) stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [muted]);

  const playNext = useCallback(() => {
    const next = queueRef.current.shift();
    if (!next) {
      setIsSpeaking(false);
      return;
    }
    const audio = new Audio(next);
    audioRef.current = audio;
    audio.onended = () => playNext();
    audio.onerror = () => playNext();
    setIsSpeaking(true);
    void audio.play().catch(() => playNext());
  }, []);

  const enqueue = useCallback(
    (base64: string, mime = "audio/wav") => {
      if (mutedRef.current) return;
      queueRef.current.push(`data:${mime};base64,${base64}`);
      if (!audioRef.current || audioRef.current.ended) playNext();
    },
    [playNext],
  );

  function stop() {
    queueRef.current = [];
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsSpeaking(false);
  }

  return { isSpeaking, muted, setMuted, enqueue, stop };
}
