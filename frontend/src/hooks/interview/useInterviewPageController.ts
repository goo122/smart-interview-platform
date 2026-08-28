import { useInterviewCameraState } from "@/hooks/interview/camera/useInterviewCameraState";
import { useInterviewResumeAnalysis } from "@/hooks/interview/resume/useInterviewResumeAnalysis";
import { useInterviewSessionFlow } from "@/hooks/interview/session/useInterviewSessionFlow";
import { useAppSelector } from "@/store/hooks";

export function useInterviewPageController() {
  const { currentUser } = useAppSelector((state) => state.user);

  const sessionFlow = useInterviewSessionFlow(currentUser);
  const resumeAnalysis = useInterviewResumeAnalysis({
    interviewerSessionId: sessionFlow.interviewerSessionId,
    setInterviewerSessionId: sessionFlow.setInterviewerSessionId,
    syncNextQuestion: (sessionId) => sessionFlow.syncNextQuestion(sessionId),
    resetInterviewFlow: sessionFlow.resetInterviewFlow,
    clearInterviewError: sessionFlow.clearInterviewError,
  });
  const cameraState = useInterviewCameraState();

  return {
    chat: {
      messages: sessionFlow.messages,
      input: sessionFlow.input,
      setInput: sessionFlow.setInput,
      isReady: sessionFlow.isReady,
      isSubmitting: sessionFlow.isInterviewSubmitting,
      handleSend: sessionFlow.handleSend,
    },
    interview: {
      sessionId: sessionFlow.interviewerSessionId,
      error: sessionFlow.interviewError,
      isEnding: sessionFlow.isEndingInterview,
      currentQuestionNumber: sessionFlow.currentQuestionNumber,
      currentQuestionContent: sessionFlow.currentQuestionContent,
      isCurrentQuestionFollowUp: sessionFlow.isCurrentQuestionFollowUp,
      currentFollowUpCount: sessionFlow.currentFollowUpCount,
      isFinished: sessionFlow.isInterviewFinished,
      totalScore: sessionFlow.totalInterviewScore,
      handleEndInterview: sessionFlow.handleEndInterview,
    },
    resume: {
      fileInputRef: resumeAnalysis.fileInputRef,
      isUploading: resumeAnalysis.isResumeUploading,
      uploadStage: resumeAnalysis.resumeUploadStage,
      localFile: resumeAnalysis.resumeLocalFile,
      fileUrl: resumeAnalysis.resumeFileUrl,
      name: resumeAnalysis.resumeName,
      uploadError: resumeAnalysis.resumeUploadError,
      previewSource: resumeAnalysis.resumePreviewSource,
      previewError: resumeAnalysis.resumePreviewError,
      previewUrl: resumeAnalysis.resumeOpenPreviewUrl,
      numPages: resumeAnalysis.numPages,
      score: resumeAnalysis.resumeScore,
      interviewTypeLabel: resumeAnalysis.resolvedInterviewTypeLabel,
      suggestions: resumeAnalysis.resumeSuggestions,
      isPreviewOpen: resumeAnalysis.isResumeOpen,
      setIsPreviewOpen: resumeAnalysis.setIsResumeOpen,
      handlePreviewLoadSuccess: resumeAnalysis.handleResumePreviewLoadSuccess,
      handlePreviewLoadError: resumeAnalysis.handleResumePreviewLoadError,
      handleFileSelect: resumeAnalysis.handleResumeFileSelect,
    },
    camera: {
      isOpen: cameraState.isCameraOpen,
      isExpanded: cameraState.isCameraExpanded,
      errorCopy: cameraState.cameraErrorCopy,
      handleCameraError: cameraState.handleCameraError,
      handleToggleCamera: cameraState.handleToggleCamera,
      handleToggleExpanded: cameraState.handleToggleCameraExpanded,
    },
  };
}
