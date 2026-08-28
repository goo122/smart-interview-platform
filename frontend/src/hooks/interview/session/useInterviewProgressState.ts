import { useCallback, useState } from "react";
import type { InterviewProgressPatch } from "@/hooks/interview/session/interviewSessionFlow.shared";

export function useInterviewProgressState() {
  const [currentQuestionNumber, setCurrentQuestionNumber] = useState<
    string | null
  >(null);
  const [currentQuestionContent, setCurrentQuestionContent] = useState<
    string | null
  >(null);
  const [isCurrentQuestionFollowUp, setIsCurrentQuestionFollowUp] =
    useState(false);
  const [currentFollowUpCount, setCurrentFollowUpCount] = useState(0);
  const [isInterviewFinished, setIsInterviewFinished] = useState(false);
  const [totalInterviewScore, setTotalInterviewScore] = useState<number | null>(
    null,
  );

  const applyProgressPatch = useCallback((patch: InterviewProgressPatch) => {
    setCurrentQuestionNumber(patch.currentQuestionNumber);
    setCurrentQuestionContent(patch.currentQuestionContent);
    setIsCurrentQuestionFollowUp(patch.isCurrentQuestionFollowUp);
    setCurrentFollowUpCount(patch.currentFollowUpCount);
    setIsInterviewFinished(patch.isInterviewFinished);
    if (patch.totalInterviewScore !== undefined) {
      setTotalInterviewScore(patch.totalInterviewScore);
    }
  }, []);

  const resetProgressState = useCallback(() => {
    setCurrentQuestionNumber(null);
    setCurrentQuestionContent(null);
    setIsCurrentQuestionFollowUp(false);
    setCurrentFollowUpCount(0);
    setIsInterviewFinished(false);
    setTotalInterviewScore(null);
  }, []);

  return {
    currentQuestionNumber,
    currentQuestionContent,
    isCurrentQuestionFollowUp,
    currentFollowUpCount,
    isInterviewFinished,
    totalInterviewScore,
    applyProgressPatch,
    resetProgressState,
  };
}
