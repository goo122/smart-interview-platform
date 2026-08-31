import { useEffect, useRef } from "react";
import { useAudioTranscriptionController } from "@/hooks/audio/useAudioTranscriptionController";
import { useSpeechCapabilities } from "@/hooks/audio/useSpeechCapabilities";
import { useAppSelector } from "@/store/hooks";

type AudioToTextComposerBridgeOptions = {
  enabled: boolean;
  isRecording: boolean;
  transcription: string;
  value: string;
  onChange: (value: string) => void;
};

export function useAudioToTextComposerBridge({
  enabled,
  isRecording,
  transcription,
  value,
  onChange,
}: AudioToTextComposerBridgeOptions) {
  const baseInputRef = useRef("");
  const prevRecordingRef = useRef(false);
  const pendingFinalFlushRef = useRef(false);

  useEffect(() => {
    if (!enabled) {
      prevRecordingRef.current = false;
      pendingFinalFlushRef.current = false;
      return;
    }

    if (isRecording && !prevRecordingRef.current) {
      baseInputRef.current = value;
      pendingFinalFlushRef.current = true;
    }

    if (!isRecording && prevRecordingRef.current) {
      // The provider may send its final snapshot just after the recording
      // state changes to false. Keep the bridge alive until that snapshot is
      // applied to the composer.
      pendingFinalFlushRef.current = true;
    }

    prevRecordingRef.current = isRecording;
  }, [enabled, isRecording, value]);

  useEffect(() => {
    if (!enabled || (!isRecording && !pendingFinalFlushRef.current)) return;

    const normalized = transcription.trim();
    if (!normalized) return;

    const base = baseInputRef.current;
    const separator = base && !base.endsWith("\n") ? "\n" : "";
    const merged = `${base}${separator}${normalized}`;

    if (merged !== value) {
      onChange(merged);
    }

    if (!isRecording) {
      pendingFinalFlushRef.current = false;
    }
  }, [enabled, isRecording, transcription, value, onChange]);
}

export function useAudioToText() {
  const { currentUser } = useAppSelector((state) => state.user);
  const speech = useSpeechCapabilities(currentUser);

  return useAudioTranscriptionController(currentUser, {
    capabilities: speech.capabilities,
    capabilitiesLoading: speech.isLoading,
    availabilityMessage: speech.availabilityMessage,
  });
}
