import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAudioToText } from "@/hooks/useAudioToText";
import { mergeTranscriptionBuffers } from "@/components/interview/sketchpad/sketchpadTypes";

type UseInterviewSketchpadTranscriptionParams = {
  notes: string;
  transcriptionBuffer: string;
  setNotes: (value: string) => void;
  setTranscriptionBuffer: (value: string) => void;
  onInsertNotes: (notes: string) => void;
  onOpenChange: (open: boolean) => void;
};

export function useInterviewSketchpadTranscription({
  notes,
  transcriptionBuffer,
  setNotes,
  setTranscriptionBuffer,
  onInsertNotes,
  onOpenChange,
}: UseInterviewSketchpadTranscriptionParams) {
  const [recordingBaseBuffer, setRecordingBaseBuffer] = useState(
    transcriptionBuffer,
  );
  const {
    isRecording,
    transcription,
    error: transcriptionError,
    startRecording,
    stopRecording,
  } = useAudioToText();

  const liveTranscriptionBuffer = useMemo(
    () =>
      isRecording
        ? mergeTranscriptionBuffers(recordingBaseBuffer, transcription)
        : transcriptionBuffer,
    [isRecording, recordingBaseBuffer, transcription, transcriptionBuffer],
  );

  const latestLiveTranscriptionRef = useRef(transcriptionBuffer);
  const previousRecordingRef = useRef(isRecording);

  const commitTranscriptionBuffer = useCallback(
    (nextBuffer: string) => {
      const normalizedBuffer = nextBuffer.trim();
      latestLiveTranscriptionRef.current = normalizedBuffer;
      setTranscriptionBuffer(normalizedBuffer);
      setRecordingBaseBuffer(normalizedBuffer);
    },
    [setTranscriptionBuffer],
  );

  useEffect(() => {
    if (isRecording) {
      latestLiveTranscriptionRef.current = liveTranscriptionBuffer;
    } else {
      latestLiveTranscriptionRef.current = transcriptionBuffer;
    }
  }, [isRecording, liveTranscriptionBuffer, transcriptionBuffer]);

  useEffect(() => {
    if (!isRecording && previousRecordingRef.current) {
      const finalizedTranscriptionBuffer = latestLiveTranscriptionRef.current;
      queueMicrotask(() => {
        commitTranscriptionBuffer(finalizedTranscriptionBuffer);
      });
    }

    previousRecordingRef.current = isRecording;
  }, [commitTranscriptionBuffer, isRecording]);

  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      commitTranscriptionBuffer(liveTranscriptionBuffer);
      stopRecording();
      return;
    }

    latestLiveTranscriptionRef.current = transcriptionBuffer;
    setRecordingBaseBuffer(transcriptionBuffer);
    await startRecording();
  }, [
    commitTranscriptionBuffer,
    isRecording,
    liveTranscriptionBuffer,
    startRecording,
    stopRecording,
    transcriptionBuffer,
  ]);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && isRecording) {
        commitTranscriptionBuffer(liveTranscriptionBuffer);
        stopRecording();
      }

      onOpenChange(nextOpen);
    },
    [
      commitTranscriptionBuffer,
      isRecording,
      liveTranscriptionBuffer,
      onOpenChange,
      stopRecording,
    ],
  );

  const appendTranscriptionToNotes = useCallback(() => {
    const normalizedTranscription = liveTranscriptionBuffer.trim();
    if (!normalizedTranscription) {
      return;
    }

    const baseNotes = notes.trim();
    setNotes(
      baseNotes
        ? `${baseNotes}\n\n${normalizedTranscription}`
        : normalizedTranscription,
    );
  }, [liveTranscriptionBuffer, notes, setNotes]);

  const copyTranscription = useCallback(async () => {
    if (
      !liveTranscriptionBuffer.trim() ||
      typeof navigator === "undefined" ||
      !navigator.clipboard
    ) {
      return;
    }

    try {
      await navigator.clipboard.writeText(liveTranscriptionBuffer.trim());
    } catch (error) {
      console.error("Failed to copy transcription buffer:", error);
    }
  }, [liveTranscriptionBuffer]);

  const clearTranscription = useCallback(() => {
    if (isRecording) {
      return;
    }

    latestLiveTranscriptionRef.current = "";
    setRecordingBaseBuffer("");
    setTranscriptionBuffer("");
  }, [isRecording, setTranscriptionBuffer]);

  const clearNotes = useCallback(() => {
    setNotes("");
  }, [setNotes]);

  const insertNotes = useCallback(() => {
    const normalizedNotes = notes.trim();
    if (!normalizedNotes) {
      return;
    }

    onInsertNotes(normalizedNotes);
  }, [notes, onInsertNotes]);

  const updateTranscriptionBuffer = useCallback(
    (value: string) => {
      latestLiveTranscriptionRef.current = value;
      setRecordingBaseBuffer(value);
      setTranscriptionBuffer(value);
    },
    [setTranscriptionBuffer],
  );

  return {
    displayedTranscriptionBuffer: liveTranscriptionBuffer,
    hasTranscriptionBuffer: liveTranscriptionBuffer.trim().length > 0,
    isRecording,
    transcriptionError,
    toggleRecording,
    appendTranscriptionToNotes,
    copyTranscription,
    clearTranscription,
    clearNotes,
    insertNotes,
    handleOpenChange,
    setTranscriptionBuffer: updateTranscriptionBuffer,
  };
}
