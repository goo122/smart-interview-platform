import { useCallback, useState } from "react";

export function useInterviewUploadStage() {
  const [isResumeUploading, setIsResumeUploading] = useState(false);
  const [resumeUploadStage, setResumeUploadStage] = useState(0);

  const startUploadStage = useCallback(() => {
    setResumeUploadStage(0);
    setIsResumeUploading(true);
  }, []);

  const setUploadStage = useCallback((stage: number) => {
    setResumeUploadStage(Math.min(Math.max(Math.round(stage), 0), 2));
  }, []);

  const finishUploadStage = useCallback(() => {
    setIsResumeUploading(false);
  }, []);

  return {
    isResumeUploading,
    resumeUploadStage,
    startUploadStage,
    setUploadStage,
    finishUploadStage,
  };
}
