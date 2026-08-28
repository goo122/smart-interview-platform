import { useCallback, useEffect, useRef, useState } from "react";
import { normalizeMediaError, type MediaError } from "@/lib/media";

type UseMicrophoneRecordingOptions = {
  audioConstraints?: MediaTrackConstraints;
  onStart?: (stream: MediaStream) => void;
  onStop?: () => void;
  onError?: (error: MediaError) => void;
};

export function useMicrophoneRecording({
  audioConstraints,
  onStart,
  onStop,
  onError,
}: UseMicrophoneRecordingOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const stop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }

    analyserRef.current = null;
    setLevel(0);
    setIsRecording(false);
    onStop?.();
  }, [onStop]);

  const start = useCallback(async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        onError?.({ kind: "not_supported" });
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: audioConstraints ?? true,
      });
      streamRef.current = stream;

      const AudioCtx =
        window.AudioContext ||
        (window as typeof window & { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!AudioCtx) {
        onError?.({ kind: "not_supported" });
        return;
      }

      const audioContext = new AudioCtx();
      audioContextRef.current = audioContext;
      await audioContext.resume().catch(() => undefined);

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.85;
      analyserRef.current = analyser;

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      const data = new Uint8Array(analyser.fftSize);
      let lastUpdate = 0;
      const update = (time: number) => {
        if (time - lastUpdate >= 120) {
          analyser.getByteTimeDomainData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i += 1) {
            const value = (data[i] - 128) / 128;
            sum += value * value;
          }
          const rms = Math.sqrt(sum / data.length);
          setLevel(rms);
          lastUpdate = time;
        }

        rafRef.current = requestAnimationFrame(update);
      };

      rafRef.current = requestAnimationFrame(update);
      setIsRecording(true);
      onStart?.(stream);
    } catch (error) {
      onError?.(normalizeMediaError(error));
      stop();
    }
  }, [audioConstraints, onError, onStart, stop]);

  const toggle = useCallback(() => {
    if (isRecording) {
      stop();
      return;
    }
    void start();
  }, [isRecording, start, stop]);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    isRecording,
    level,
    toggle,
    stop,
    start,
  };
}
