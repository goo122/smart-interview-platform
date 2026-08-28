export type SketchpadDraft = {
  notes: string;
  transcriptionBuffer: string;
  transcriptionCommitted: boolean;
  updatedAt: number;
};

export type SketchpadQuestionViewState = {
  questionNumber: string | null;
  questionContent: string | null;
  isFinished: boolean;
  isSyncing: boolean;
  isCollapsed: boolean;
};

export type SketchpadActions = {
  setNotes: (value: string) => void;
  setTranscriptionBuffer: (value: string) => void;
  toggleRecording: () => Promise<void>;
  appendTranscriptionToNotes: () => void;
  copyTranscription: () => Promise<void>;
  clearTranscription: () => void;
  clearNotes: () => void;
  insertNotes: () => void;
  setCollapsed: (value: boolean) => void;
  handleOpenChange: (open: boolean) => void;
};

export const STORAGE_VERSION = "v2";

export const EMPTY_SKETCHPAD_DRAFT: SketchpadDraft = {
  notes: "",
  transcriptionBuffer: "",
  transcriptionCommitted: false,
  updatedAt: 0,
};

export const getSketchpadStorageKey = (sessionId: string | null) =>
  `interview-sketchpad:${STORAGE_VERSION}:${sessionId || "draft"}`;

export const mergeTranscriptionBuffers = (base: string, next: string) => {
  const normalizedBase = base.trim();
  const normalizedNext = next.trim();

  if (!normalizedBase) return normalizedNext;
  if (!normalizedNext) return normalizedBase;

  return `${normalizedBase}\n\n${normalizedNext}`;
};

export const normalizeSketchpadDraft = (
  value: Partial<SketchpadDraft> | null | undefined,
): SketchpadDraft => ({
  notes: typeof value?.notes === "string" ? value.notes : "",
  transcriptionBuffer:
    typeof value?.transcriptionBuffer === "string"
      ? value.transcriptionBuffer
      : "",
  transcriptionCommitted:
    typeof value?.transcriptionCommitted === "boolean"
      ? value.transcriptionCommitted
      : false,
  updatedAt: typeof value?.updatedAt === "number" ? value.updatedAt : 0,
});

export const createPersistedSketchpadDraft = (
  draft: SketchpadDraft,
  transcriptionBuffer: string,
): SketchpadDraft => {
  const normalizedBuffer = transcriptionBuffer.trim();

  return {
    ...draft,
    transcriptionBuffer,
    transcriptionCommitted: normalizedBuffer.length > 0,
    updatedAt: Date.now(),
  };
};
