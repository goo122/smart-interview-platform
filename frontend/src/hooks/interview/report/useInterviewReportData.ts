import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  buildInterviewReportViewModel,
  fetchInterviewReportQueryData,
} from "@/hooks/interview/report/interviewReportData.shared";

export function useInterviewReportData(reportSessionId: string | null) {
  const query = useQuery({
    queryKey: ["interview-record", reportSessionId],
    enabled: Boolean(reportSessionId),
    queryFn: () => fetchInterviewReportQueryData(reportSessionId as string),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  const recordError = useMemo(() => {
    if (!query.error) return null;
    return query.error instanceof Error
      ? query.error.message
      : "加载面试报告时发生错误，请稍后重试。";
  }, [query.error]);

  const reportViewModel = useMemo(
    () => buildInterviewReportViewModel(query.data?.record ?? null),
    [query.data?.record],
  );

  return {
    isRecordLoading: query.isLoading || query.isFetching,
    recordError,
    ...reportViewModel,
  };
}
