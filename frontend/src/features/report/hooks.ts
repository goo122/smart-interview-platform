import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { ApiError } from "@/api/errors";
import { reportApi } from "@/features/report/api";
import { asReportStatus } from "@/features/report/types";

export const reportKeys = {
  all: ["report"] as const,
  list: (current: number, size: number) => [...reportKeys.all, "list", current, size] as const,
  session: (sessionId: string) => [...reportKeys.all, "session", sessionId] as const,
  detail: (reportId: string) => [...reportKeys.all, "detail", reportId] as const,
};

const reportPollInterval = (status: string | undefined) =>
  status === "PENDING" ? 2_000 : status === "GENERATING" ? 2_500 : false;

export function useReports(current: number, size = 10) {
  return useQuery({
    queryKey: reportKeys.list(current, size),
    queryFn: () => reportApi.list(current, size),
    staleTime: 5_000,
    refetchInterval: (query) => {
      const hasPendingReport = query.state.data?.records.some((report) =>
        report.status === "PENDING" || report.status === "GENERATING",
      );
      return hasPendingReport ? 2_000 : false;
    },
    refetchIntervalInBackground: false,
  });
}

export function useSessionReport(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: reportKeys.session(sessionId),
    queryFn: () => reportApi.getForSession(sessionId),
    enabled: enabled && Boolean(sessionId),
    staleTime: 1_000,
    refetchInterval: (query) => reportPollInterval(query.state.data?.status),
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useReport(reportId: string, enabled = true) {
  return useQuery({
    queryKey: reportKeys.detail(reportId),
    queryFn: () => reportApi.get(reportId),
    enabled: enabled && Boolean(reportId),
    staleTime: 5_000,
    refetchInterval: (query) => reportPollInterval(query.state.data?.status),
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useReportGeneration() {
  const queryClient = useQueryClient();
  const inFlight = useRef(new Map<string, ReturnType<typeof reportApi.generateForSession>>());
  const generate = useMutation({
    mutationFn: async (sessionId: string) => {
      const existing = inFlight.current.get(sessionId);
      if (existing) return existing;
      const request = reportApi.generateForSession(sessionId);
      inFlight.current.set(sessionId, request);
      try {
        return await request;
      } finally {
        inFlight.current.delete(sessionId);
      }
    },
    onSuccess: async (report) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: reportKeys.session(report.sessionId) }),
        queryClient.invalidateQueries({ queryKey: reportKeys.detail(report.reportId) }),
        queryClient.invalidateQueries({ queryKey: reportKeys.all }),
      ]);
    },
  });
  return generate;
}

export function useAutomaticReportGeneration(
  sessionId: string,
  shouldGenerate: boolean,
  reportQuery: ReturnType<typeof useSessionReport>,
) {
  const generate = useReportGeneration();
  const requested = useRef(false);
  useEffect(() => {
    if (
      shouldGenerate &&
      reportQuery.isError &&
      reportQuery.error instanceof ApiError &&
      reportQuery.error.status === 404 &&
      !requested.current
    ) {
      requested.current = true;
      generate.mutate(sessionId);
    }
  }, [generate, reportQuery.error, reportQuery.isError, sessionId, shouldGenerate]);
  return generate;
}

export function normalizeReportStatus(status: string): ReturnType<typeof asReportStatus> {
  return asReportStatus(status);
}
