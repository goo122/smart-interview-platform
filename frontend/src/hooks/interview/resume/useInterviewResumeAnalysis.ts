import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import { interviewService } from "@/services/interviewService";
import {
  buildResumeMetadata,
  deriveResumeName,
  isPdfResumeFile,
} from "@/hooks/interview/resume/interviewResumeAnalysis.shared";
import { resolveInterviewTypeLabel } from "@/hooks/interview/shared/interviewUtils";
import { useInterviewResumePreviewState } from "@/hooks/interview/resume/useInterviewResumePreviewState";
import { useInterviewUploadStage } from "@/hooks/interview/resume/useInterviewUploadStage";

type UseInterviewResumeAnalysisOptions = {
  interviewerSessionId: string | null;
  setInterviewerSessionId: (sessionId: string | null) => void;
  syncNextQuestion: (sessionId: string) => Promise<void>;
  resetInterviewFlow: () => void;
  clearInterviewError: () => void;
};

export function useInterviewResumeAnalysis({
  interviewerSessionId,
  setInterviewerSessionId,
  syncNextQuestion,
  resetInterviewFlow,
  clearInterviewError,
}: UseInterviewResumeAnalysisOptions) {
  const [resumeScore, setResumeScore] = useState<number | null>(null);
  const [resumeInterviewType, setResumeInterviewType] = useState<string | null>(
    null,
  );
  const [resumeSuggestions, setResumeSuggestions] = useState<string[]>([]);
  const [resumeUploadError, setResumeUploadError] = useState<string | null>(
    null,
  );
  const [isResumeOpen, setIsResumeOpen] = useState(false);

  const {
    resumeName,
    setResumeName,
    resumeFileUrl,
    resumeRemoteFile,
    resumeLocalFile,
    setResumeLocalFile,
    resumePreviewError,
    setResumePreviewError,
    numPages,
    setNumPages,
    resumePreviewSource,
    resumeOpenPreviewUrl,
    replaceRemoteResumePreview,
    clearRemoteResumePreview,
    clearPreviewState,
    handleResumePreviewLoadSuccess,
    handleResumePreviewLoadError,
  } = useInterviewResumePreviewState();
  const {
    isResumeUploading,
    resumeUploadStage,
    startUploadStage,
    finishUploadStage,
  } = useInterviewUploadStage();

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const hydratedSessionIdRef = useRef<string | null>(null);

  const resolvedInterviewTypeLabel =
    resolveInterviewTypeLabel(resumeInterviewType);

  const resetResumeMetadata = useCallback(() => {
    setResumeScore(null);
    setResumeInterviewType(null);
    setResumeSuggestions([]);
    setResumeUploadError(null);
  }, []);

  const applyResumeMetadata = useCallback(
    (metadata: {
      resumeName?: string | null;
      resumeScore: number | null;
      resumeInterviewType: string | null;
      resumeSuggestions: string[];
    }) => {
      setResumeName(metadata.resumeName ?? null);
      setResumeScore(metadata.resumeScore);
      setResumeInterviewType(metadata.resumeInterviewType);
      setResumeSuggestions(metadata.resumeSuggestions);
    },
    [setResumeName],
  );

  useEffect(() => {
    if (!interviewerSessionId) {
      hydratedSessionIdRef.current = null;
      return;
    }

    if (hydratedSessionIdRef.current === interviewerSessionId) {
      return;
    }

    clearPreviewState();
    resetResumeMetadata();
  }, [clearPreviewState, interviewerSessionId, resetResumeMetadata]);

  useEffect(() => {
    if (!interviewerSessionId || isResumeUploading) {
      return;
    }
    if (hydratedSessionIdRef.current === interviewerSessionId) {
      return;
    }

    let cancelled = false;

    const hydrateResumeState = async () => {
      try {
        const restored =
          await interviewService.restoreInterviewSession(interviewerSessionId);
        if (cancelled) {
          return;
        }

        applyResumeMetadata(
          buildResumeMetadata({
            resumeScore: restored.resumeScore,
            interviewType: restored.interviewType,
            suggestions: restored.suggestions,
            resumeFileUrl: restored.resumeFileUrl,
          }),
        );
        setResumePreviewError(null);

        try {
          const previewBlob =
            await interviewService.fetchInterviewResumePreviewBlob(
              interviewerSessionId,
            );
          if (cancelled) {
            return;
          }

          replaceRemoteResumePreview(
            previewBlob,
            URL.createObjectURL(previewBlob),
            deriveResumeName(restored.resumeFileUrl) || "resume.pdf",
          );
        } catch (error) {
          if (cancelled) {
            return;
          }
          clearRemoteResumePreview();
          const message =
            error instanceof Error
              ? error.message
              : "Failed to load resume preview";
          setResumePreviewError(message);
          console.error("Failed to load interview resume preview:", error);
        }

        hydratedSessionIdRef.current = interviewerSessionId;
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.error("Failed to restore interview session metadata:", error);
      }
    };

    void hydrateResumeState();

    return () => {
      cancelled = true;
    };
  }, [
    clearRemoteResumePreview,
    interviewerSessionId,
    isResumeUploading,
    replaceRemoteResumePreview,
    applyResumeMetadata,
    setResumePreviewError,
  ]);

  const handleResumeFileSelect = async (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (!isPdfResumeFile(file)) {
      setResumeUploadError("Only PDF files are supported");
      return;
    }

    setResumeUploadError(null);
    setResumePreviewError(null);
    clearInterviewError();
    resetInterviewFlow();

    resetResumeMetadata();
    setResumeName(file.name);
    setResumeLocalFile(file);
    clearRemoteResumePreview();
    setNumPages(1);
    setIsResumeOpen(false);
    hydratedSessionIdRef.current = null;
    startUploadStage();

    try {
      const createdSession = await interviewService.createInterviewSession();
      const sessionId = createdSession.sessionId;

      const analyzed = await interviewService.extractInterviewQuestions({
        sessionId,
        resumePdf: file,
      });

      if (analyzed.isSuccess === 0) {
        throw new Error(
          analyzed.errorMessage || "Failed to analyze resume, please retry",
        );
      }

      applyResumeMetadata(
        buildResumeMetadata({
          resumeScore: analyzed.resumeScore,
          interviewType: analyzed.interviewType,
          suggestions: analyzed.suggestions ?? null,
          resumeFileUrl: file.name,
        }),
      );
      setInterviewerSessionId(sessionId);
      hydratedSessionIdRef.current = sessionId;
      setResumePreviewError(null);

      try {
        const previewBlob =
          await interviewService.fetchInterviewResumePreviewBlob(sessionId);
        replaceRemoteResumePreview(
          previewBlob,
          URL.createObjectURL(previewBlob),
          file.name,
        );
      } catch (error) {
        console.error(
          "Failed to fetch proxied resume preview after upload:",
          error,
        );
      }

      await syncNextQuestion(sessionId);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to upload resume, please retry";
      setResumeUploadError(message);
      clearRemoteResumePreview();
      setInterviewerSessionId(null);
    } finally {
      finishUploadStage();
    }
  };

  return {
    fileInputRef,
    resumeName,
    resumeFileUrl,
    resumeRemoteFile,
    resumeLocalFile,
    resumeScore,
    resumeInterviewType,
    resumeSuggestions,
    resumePreviewError,
    resumeUploadError,
    isResumeUploading,
    resumeUploadStage,
    numPages,
    isResumeOpen,
    setIsResumeOpen,
    resumePreviewSource,
    resumeOpenPreviewUrl,
    resolvedInterviewTypeLabel,
    handleResumePreviewLoadSuccess,
    handleResumePreviewLoadError,
    handleResumeFileSelect,
  };
}
