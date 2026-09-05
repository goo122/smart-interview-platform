import { startTransition, useCallback, useRef, useState } from "react";
import type { CameraPreviewHandle } from "@/components/camera/CameraPreview";
import ChatRoom from "@/components/chat/ChatRoom";
import SmartComposer from "@/components/chat/SmartComposer";
import InterviewCameraOverlay from "@/components/interview/InterviewCameraOverlay";
import InterviewHeader from "@/components/interview/InterviewHeader";
import InterviewResumePreviewDialog from "@/components/interview/InterviewResumePreviewDialog";
import InterviewResumeReferenceCard from "@/components/interview/InterviewResumeReferenceCard";
import InterviewResumeUploadCard from "@/components/interview/InterviewResumeUploadCard";
import InterviewSketchpadSheet from "@/components/interview/sketchpad/InterviewSketchpadSheet";
import { useInterviewDemeanorPolling } from "@/hooks/interview/camera/useInterviewDemeanorPolling";
import { useInterviewPageController } from "@/hooks/interview/useInterviewPageController";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export default function InterviewPage() {
  const cameraPreviewRef = useRef<CameraPreviewHandle | null>(null);
  const [isSketchpadOpen, setIsSketchpadOpen] = useState(false);
  const { chat, interview, resume, camera } = useInterviewPageController();
  const { setInput, isReady, isSubmitting, handleSend, input, messages } = chat;
  const { setIsPreviewOpen } = resume;

  const captureFrame = useCallback(async () => {
    return cameraPreviewRef.current?.captureFrame() ?? null;
  }, []);

  const handleInsertNotes = useCallback(
    (notes: string) => {
      if (!notes.trim()) return;
      setInput((prev) => (prev.trim() ? `${prev.trim()}\n\n${notes}` : notes));
      setIsSketchpadOpen(false);
    },
    [setInput],
  );

  const handleOpenSketchpad = useCallback(() => {
    startTransition(() => {
      setIsSketchpadOpen(true);
    });
  }, []);

  const handleOpenResume = useCallback(() => {
    startTransition(() => {
      setIsPreviewOpen(true);
    });
  }, [setIsPreviewOpen]);

  const demeanorPolling = useInterviewDemeanorPolling({
    sessionId: interview.sessionId,
    enabled:
      Boolean(interview.sessionId) &&
      isReady &&
      camera.isOpen &&
      !interview.isFinished &&
      !interview.isEnding,
    captureFrame,
  });

  return (
    <>
      <ChatRoom
        header={
          <InterviewHeader
            isReady={isReady}
            hasSession={Boolean(interview.sessionId)}
            isRecovering={interview.isRecovering}
            currentQuestionNumber={interview.currentQuestionNumber}
            isCurrentQuestionFollowUp={interview.isCurrentQuestionFollowUp}
            currentFollowUpCount={interview.currentFollowUpCount}
            isInterviewFinished={interview.isFinished}
            totalInterviewScore={interview.totalScore}
            isCameraOpen={camera.isOpen}
            isEndingInterview={interview.isEnding || isSubmitting || interview.isRecovering}
            onToggleCamera={camera.handleToggleCamera}
            onOpenSketchpad={handleOpenSketchpad}
            onEndInterview={interview.handleEndInterview}
          />
        }
        topContent={
          <div className="space-y-4">
            {interview.isRecovering ? (
              <p role="status" className="text-sm text-slate-500">
                正在同步面试进度，等待当前题目准备完成…
              </p>
            ) : null}
            {interview.error && interview.sessionId ? (
              <div className="flex gap-2">
                <Button variant="outline" onClick={interview.retryRecovery} disabled={interview.isRecovering}>
                  重新同步面试
                </Button>
                <Button variant="outline" asChild>
                  <Link to="/interview">返回面试列表</Link>
                </Button>
              </div>
            ) : null}
            <InterviewResumeUploadCard
              fileInputRef={resume.fileInputRef}
              isResumeUploading={resume.isUploading}
              showUploadButton={!interview.sessionId}
              resumeUploadStage={resume.uploadStage}
              resumeLocalFile={resume.localFile}
              resumeFileUrl={resume.fileUrl}
              resumeName={resume.name}
              resumePreviewError={resume.previewError}
              resumeUploadError={resume.uploadError}
              interviewError={interview.error}
              onResumeFileSelect={resume.handleFileSelect}
              onOpenResume={handleOpenResume}
            />
            <InterviewResumePreviewDialog
              open={resume.isPreviewOpen}
              onOpenChange={resume.setIsPreviewOpen}
              resumePreviewSource={resume.previewSource}
              resumePreviewError={resume.previewError}
              resumeOpenPreviewUrl={resume.previewUrl}
              numPages={resume.numPages}
              resumeScore={resume.score}
              resolvedInterviewTypeLabel={resume.interviewTypeLabel}
              resumeSuggestions={resume.suggestions}
              onLoadSuccess={resume.handlePreviewLoadSuccess}
              onLoadError={resume.handlePreviewLoadError}
            />
          </div>
        }
        messages={messages}
        inputValue={input}
        onInputChange={setInput}
        onSend={handleSend}
        customComposer={
          <SmartComposer
            value={input}
            onChange={setInput}
            onSend={handleSend}
            placeholder="输入你的回答，或点击麦克风开始语音作答..."
            disabled={!isReady || isSubmitting || resume.isUploading || interview.isEnding}
            showDefaultLeading={false}
          />
        }
        contentOverlay={
          camera.isOpen ? (
          <InterviewCameraOverlay
            ref={cameraPreviewRef}
            isCameraExpanded={camera.isExpanded}
            cameraErrorCopy={camera.errorCopy}
            onCameraError={camera.handleCameraError}
            onToggleExpanded={camera.handleToggleExpanded}
            demeanorStatus={demeanorPolling.status}
            latestDemeanorEvaluation={demeanorPolling.latestEvaluation}
          />
          ) : null
        }
        footer={
          <div className="mt-2 space-y-2">
            <p className="text-center text-xs text-slate-400">
              AI 生成内容可能存在误差，请以实际情况为准。
            </p>
          </div>
        }
      />

      <InterviewSketchpadSheet
        open={isSketchpadOpen}
        onOpenChange={setIsSketchpadOpen}
        sessionId={interview.sessionId}
        currentQuestionNumber={interview.currentQuestionNumber}
        currentQuestionContent={interview.currentQuestionContent}
        onInsertNotes={handleInsertNotes}
      />
      <InterviewResumeReferenceCard
        key={[
          interview.sessionId ?? "no-session",
          resume.name ?? "no-resume",
          resume.previewUrl ?? "no-preview-url",
        ].join(":")}
        open={isSketchpadOpen}
        resumeName={resume.name}
        resumePreviewSource={resume.previewSource}
        resumePreviewError={resume.previewError}
        resumeOpenPreviewUrl={resume.previewUrl}
        numPages={resume.numPages}
        onLoadSuccess={resume.handlePreviewLoadSuccess}
        onLoadError={resume.handlePreviewLoadError}
      />
    </>
  );
}
