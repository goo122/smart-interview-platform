import { useCallback, useEffect, useRef, useState } from "react";

export function useInterviewUploadStage() {
  const [isResumeUploading, setIsResumeUploading] = useState(false);
  const [resumeUploadStage, setResumeUploadStage] = useState(0);
  const uploadStageTimersRef = useRef<number[]>([]);

  const clearUploadStageTimers = useCallback(() => {
    uploadStageTimersRef.current.forEach((timerId) => {
      window.clearTimeout(timerId);
    });
    uploadStageTimersRef.current = [];
  }, []);

  const startUploadStage = useCallback(() => {
    setResumeUploadStage(0);
    setIsResumeUploading(true);
    clearUploadStageTimers();

    uploadStageTimersRef.current = [
      window.setTimeout(() => {
        setResumeUploadStage(1);
      }, 600),
      window.setTimeout(() => {
        setResumeUploadStage(2);
      }, 1800),
    ];
  }, [clearUploadStageTimers]);

  const finishUploadStage = useCallback(() => {
    clearUploadStageTimers();
    setIsResumeUploading(false);
  }, [clearUploadStageTimers]);

  useEffect(
    () => () => {
      clearUploadStageTimers();
    },
    [clearUploadStageTimers],
  );

  return {
    isResumeUploading,
    resumeUploadStage,
    startUploadStage,
    finishUploadStage,
  };
}
