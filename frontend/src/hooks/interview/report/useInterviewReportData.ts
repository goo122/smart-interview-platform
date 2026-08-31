import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  buildInterviewReportViewModel,
  fetchInterviewReportQueryData,
} from "@/hooks/interview/report/interviewReportData.shared";
import { interviewService } from "@/services/interviewService";

export function useInterviewReportData(reportSessionId: string | null) {
  const queryClient = useQueryClient();
  const queryKey = ["interview-record", reportSessionId];
  const query = useQuery({
    queryKey,
    enabled: Boolean(reportSessionId),
    queryFn: () => fetchInterviewReportQueryData(reportSessionId as string),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 0,
    refetchInterval: (currentQuery) => {
      const status =
        currentQuery.state.data?.record?.interviewStatus?.toUpperCase();
      return status === "PENDING" || status === "GENERATING" ? 1500 : false;
    },
  });

  const reportStatus =
    query.data?.record?.interviewStatus?.toUpperCase() ?? null;
  const isReportGenerating =
    reportStatus === "PENDING" || reportStatus === "GENERATING";

  const retryMutation = useMutation({
    mutationFn: () =>
      interviewService.generateInterviewReport(reportSessionId as string),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const recordError = useMemo(() => {
    if (query.error) {
      return query.error instanceof Error
        ? query.error.message
        : "加载面试报告时发生错误，请稍后重试。";
    }
    if (reportStatus === "FAILED") {
      return query.data?.record?.failureMessage || "报告生成失败，请重试。";
    }
    return null;
  }, [query.data?.record?.failureMessage, query.error, reportStatus]);

  const reportViewModel = useMemo(
    () => buildInterviewReportViewModel(query.data?.record ?? null),
    [query.data?.record],
  );

  return {
    isRecordLoading: query.isLoading || query.isFetching || isReportGenerating,
    recordError,
    reportStatus,
    isReportGenerating,
    isReportReady: reportStatus === "READY",
    retryReport: retryMutation.mutateAsync,
    isRetryingReport: retryMutation.isPending,
    ...reportViewModel,
  };
}
