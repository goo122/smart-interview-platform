import { useCallback, useEffect, useState } from "react";
import {
  createPersistedSketchpadDraft,
  EMPTY_SKETCHPAD_DRAFT,
  getSketchpadStorageKey,
  normalizeSketchpadDraft,
  type SketchpadDraft,
} from "@/components/interview/sketchpad/sketchpadTypes";

const readStorage = (sessionId: string | null): SketchpadDraft => {
  if (typeof window === "undefined") {
    return EMPTY_SKETCHPAD_DRAFT;
  }

  try {
    const raw = window.localStorage.getItem(getSketchpadStorageKey(sessionId));
    if (!raw) {
      return EMPTY_SKETCHPAD_DRAFT;
    }

    return normalizeSketchpadDraft(JSON.parse(raw) as Partial<SketchpadDraft>);
  } catch (error) {
    console.error("Failed to read sketchpad storage:", error);
    return EMPTY_SKETCHPAD_DRAFT;
  }
};

const persistStorage = (sessionId: string | null, draft: SketchpadDraft) => {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(
      getSketchpadStorageKey(sessionId),
      JSON.stringify(draft),
    );
  } catch (error) {
    console.error("Failed to persist sketchpad:", error);
  }
};

export function useInterviewSketchpadStorage(
  sessionId: string | null,
) {
  const [draft, setDraft] = useState<SketchpadDraft>(() => readStorage(sessionId));

  useEffect(() => {
    setDraft(readStorage(sessionId));
  }, [sessionId]);

  const persistDraft = useCallback(
    (transcriptionBuffer = draft.transcriptionBuffer) => {
      persistStorage(
        sessionId,
        createPersistedSketchpadDraft(draft, transcriptionBuffer),
      );
    },
    [draft, sessionId],
  );

  useEffect(() => {
    persistDraft();
  }, [persistDraft]);

  const updateDraft = useCallback(
    (updater: (previous: SketchpadDraft) => SketchpadDraft) => {
      setDraft((previous) => updater(previous));
    },
    [],
  );

  return {
    draft,
    setDraft,
    updateDraft,
    persistDraft,
  };
}
