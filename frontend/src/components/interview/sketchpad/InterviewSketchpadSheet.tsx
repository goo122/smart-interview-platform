import { useEffect, useMemo } from "react";
import { InterviewSketchpadSheetView } from "@/components/interview/sketchpad/InterviewSketchpadSheetView";
import { useInterviewSketchpadQuestionState } from "@/components/interview/sketchpad/useInterviewSketchpadQuestionState";
import { useInterviewSketchpadStorage } from "@/components/interview/sketchpad/useInterviewSketchpadStorage";
import { useInterviewSketchpadTranscription } from "@/components/interview/sketchpad/useInterviewSketchpadTranscription";

type InterviewSketchpadSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sessionId: string | null;
  currentQuestionNumber?: string | null;
  currentQuestionContent?: string | null;
  onInsertNotes: (notes: string) => void;
};

function InterviewSketchpadSheetContent({
  open,
  onOpenChange,
  sessionId,
  currentQuestionNumber,
  currentQuestionContent,
  onInsertNotes,
}: InterviewSketchpadSheetProps) {
  const question = useInterviewSketchpadQuestionState({
    open,
    sessionId,
    currentQuestionNumber,
    currentQuestionContent,
  });
  const { draft, updateDraft, persistDraft } = useInterviewSketchpadStorage(
    sessionId,
  );
  const notes = draft.notes;
  const storedTranscriptionBuffer = draft.transcriptionBuffer;

  const setNotes = (value: string) => {
    updateDraft((previous) => ({
      ...previous,
      notes: value,
    }));
  };

  const setTranscriptionBuffer = (value: string) => {
    updateDraft((previous) => ({
      ...previous,
      transcriptionBuffer: value,
      transcriptionCommitted: value.trim().length > 0,
    }));
  };

  const transcription = useInterviewSketchpadTranscription({
    notes,
    transcriptionBuffer: storedTranscriptionBuffer,
    setNotes,
    setTranscriptionBuffer,
    onInsertNotes,
    onOpenChange,
  });

  useEffect(() => {
    persistDraft(transcription.displayedTranscriptionBuffer);
  }, [persistDraft, transcription.displayedTranscriptionBuffer]);

  const hasNotes = notes.trim().length > 0;
  const saveHint = useMemo(() => {
    if (!hasNotes && !transcription.hasTranscriptionBuffer) {
      return "当前面试还没有构思内容。";
    }

    return "构思内容已按当前 session 自动保存在本地。";
  }, [hasNotes, transcription.hasTranscriptionBuffer]);

  return (
    <InterviewSketchpadSheetView
      open={open}
      notes={notes}
      displayedTranscriptionBuffer={transcription.displayedTranscriptionBuffer}
      question={question}
      hasNotes={hasNotes}
      hasTranscriptionBuffer={transcription.hasTranscriptionBuffer}
      isRecording={transcription.isRecording}
      transcriptionError={transcription.transcriptionError}
      saveHint={saveHint}
      actions={{
        setNotes,
        setTranscriptionBuffer: transcription.setTranscriptionBuffer,
        toggleRecording: transcription.toggleRecording,
        appendTranscriptionToNotes: transcription.appendTranscriptionToNotes,
        copyTranscription: transcription.copyTranscription,
        clearTranscription: transcription.clearTranscription,
        clearNotes: transcription.clearNotes,
        insertNotes: transcription.insertNotes,
        setCollapsed: question.setCollapsed,
        handleOpenChange: transcription.handleOpenChange,
      }}
    />
  );
}

export default function InterviewSketchpadSheet(
  props: InterviewSketchpadSheetProps,
) {
  return (
    <InterviewSketchpadSheetContent
      key={props.sessionId || "draft"}
      {...props}
    />
  );
}
