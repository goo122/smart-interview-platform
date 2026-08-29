import { useCallback, useState } from "react";
import type { InterviewProgressPatch } from "@/hooks/interview/session/interviewSessionFlow.shared";

export function useInterviewProgressState() {
  const [currentTurnId, setCurrentTurnId] = useState<string | null>(null);
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
  const [isInterviewFailed, setIsInterviewFailed] = useState(false);
  const [totalInterviewScore, setTotalInterviewScore] = useState<number | null>(
    null,
  );

  const applyProgressPatch = useCallback((patch: InterviewProgressPatch) => {
    setCurrentTurnId(patch.currentTurnId);
    setCurrentQuestionNumber(patch.currentQuestionNumber);
    setCurrentQuestionContent(patch.currentQuestionContent);
    setIsCurrentQuestionFollowUp(patch.isCurrentQuestionFollowUp);
    setCurrentFollowUpCount(patch.currentFollowUpCount);
    setIsInterviewFinished(patch.isInterviewFinished);
    setIsInterviewFailed(patch.isInterviewFailed);
    if (patch.totalInterviewScore !== undefined) {
      setTotalInterviewScore(patch.totalInterviewScore);
    }
  }, []);

  const resetProgressState = useCallback(() => {
    setCurrentTurnId(null);
    setCurrentQuestionNumber(null);
    setCurrentQuestionContent(null);
    setIsCurrentQuestionFollowUp(false);
    setCurrentFollowUpCount(0);
    setIsInterviewFinished(false);
    setIsInterviewFailed(false);
    setTotalInterviewScore(null);
  }, []);

  return {
    currentTurnId,
    currentQuestionNumber,
    currentQuestionContent,
    isCurrentQuestionFollowUp,
    currentFollowUpCount,
    isInterviewFinished,
    isInterviewFailed,
    totalInterviewScore,
    applyProgressPatch,
    resetProgressState,
  };
}
