export type AudioToTextIncomingMessage = {
  type?: string | null;
  message?: string | null;
  data?: string | null;
  isSnapshot?: boolean | null;
  updateAction?: string | null;
  timestamp?: number | null;
};

export type AudioTranscriptionEvent =
  | { kind: "reset" }
  | { kind: "replace"; text: string }
  | { kind: "archive"; text: string }
  | { kind: "connected" }
  | { kind: "control" }
  | { kind: "heartbeat" }
  | { kind: "error"; message: string }
  | { kind: "unknown"; type?: string | null };

export type AudioTranscriptionState = {
  liveText: string;
  finalText: string;
};

export const createInitialAudioTranscriptionState =
  (): AudioTranscriptionState => ({
    liveText: "",
    finalText: "",
  });

const normalizeText = (value?: string | null) => value?.trim() ?? "";

const mergeDistinctTranscription = (base: string, next: string) => {
  const normalizedBase = normalizeText(base);
  const normalizedNext = normalizeText(next);

  if (!normalizedBase) {
    return normalizedNext;
  }

  if (!normalizedNext) {
    return normalizedBase;
  }

  if (normalizedBase === normalizedNext) {
    return normalizedBase;
  }

  if (normalizedBase.includes(normalizedNext)) {
    return normalizedBase;
  }

  if (normalizedNext.includes(normalizedBase)) {
    return normalizedNext;
  }

  return `${normalizedBase}\n\n${normalizedNext}`;
};

export const resolveAudioTranscriptionEvent = (
  message: AudioToTextIncomingMessage,
): AudioTranscriptionEvent => {
  const text = normalizeText(message.data);

  if (message.updateAction === "replace" || message.type === "transcription") {
    return {
      kind: "replace",
      text,
    };
  }

  if (message.updateAction === "archive" || message.type === "final") {
    return {
      kind: "archive",
      text,
    };
  }

  switch (message.type) {
    case "connected":
      return { kind: "connected" };
    case "transcription_started":
      return { kind: "reset" };
    case "transcription_stopped":
    case "status":
      return { kind: "control" };
    case "heartbeat":
    case "pong":
      return { kind: "heartbeat" };
    case "error":
      return {
        kind: "error",
        message:
          normalizeText(message.message) || text || "Transcription error",
      };
    default:
      return {
        kind: "unknown",
        type: message.type,
      };
  }
};

export const reduceAudioTranscriptionState = (
  state: AudioTranscriptionState,
  event: AudioTranscriptionEvent,
): AudioTranscriptionState => {
  switch (event.kind) {
    case "reset":
      return createInitialAudioTranscriptionState();
    case "replace": {
      const nextLiveText = normalizeText(event.text);
      if (!nextLiveText) {
        return state;
      }

      if (
        nextLiveText === state.liveText &&
        (!state.finalText || nextLiveText === state.finalText)
      ) {
        return state;
      }

      return {
        ...state,
        liveText: nextLiveText,
      };
    }
    case "archive": {
      const archivedText =
        normalizeText(event.text) ||
        normalizeText(state.liveText) ||
        normalizeText(state.finalText);
      if (!archivedText) {
        return state;
      }

      const nextFinalText = mergeDistinctTranscription(
        state.finalText,
        archivedText,
      );
      if (nextFinalText === state.finalText && !state.liveText) {
        return state;
      }

      return {
        liveText: "",
        finalText: nextFinalText,
      };
    }
    default:
      return state;
  }
};

export const getMergedAudioTranscription = (state: AudioTranscriptionState) =>
  mergeDistinctTranscription(state.finalText, state.liveText);
