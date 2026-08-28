import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { AnswerInterviewQuestionResult } from "@/services/interviewService";
import { interviewService } from "@/services/interviewService";

type UseInterviewSketchpadQuestionStateParams = {
  open: boolean;
  sessionId: string | null;
  currentQuestionNumber?: string | null;
  currentQuestionContent?: string | null;
};

export function useInterviewSketchpadQuestionState({
  open,
  sessionId,
  currentQuestionNumber,
  currentQuestionContent,
}: UseInterviewSketchpadQuestionStateParams) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const questionQuery = useQuery<AnswerInterviewQuestionResult | null>({
    queryKey: ["interview-current-question", sessionId],
    enabled: Boolean(open && sessionId),
    queryFn: () => interviewService.getCurrentQuestion(sessionId as string),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 10_000,
  });

  return useMemo(() => {
    const serverQuestion = questionQuery.data ?? null;
    const serverQuestionNumber =
      serverQuestion?.nextQuestionNumber ||
      serverQuestion?.questionNumber ||
      null;
    const serverQuestionContent =
      serverQuestion?.questionContent?.trim() ||
      serverQuestion?.nextQuestion?.trim() ||
      null;
    const isFinished = Boolean(serverQuestion?.finished);

    return {
      questionNumber: serverQuestionNumber ?? currentQuestionNumber ?? null,
      questionContent: isFinished
        ? null
        : serverQuestionContent || currentQuestionContent?.trim() || null,
      isFinished,
      isSyncing: questionQuery.isFetching,
      isCollapsed,
      setCollapsed: setIsCollapsed,
    };
  }, [
    currentQuestionContent,
    currentQuestionNumber,
    isCollapsed,
    questionQuery.data,
    questionQuery.isFetching,
  ]);
}
