import { apiClient, requestData } from "@/api/client";
import type { InterviewReportPage, InterviewReportResponse } from "@/api/generated";

const basePath = "/xunzhi/v1/interview";

export const reportApi = {
  generateForSession: (sessionId: string) =>
    requestData(
      apiClient.post<InterviewReportResponse>(
        `${basePath}/sessions/${sessionId}/report`,
      ),
    ),
  getForSession: (sessionId: string) =>
    requestData(
      apiClient.get<InterviewReportResponse>(
        `${basePath}/sessions/${sessionId}/report`,
      ),
    ),
  list: (current = 1, size = 10) =>
    requestData(
      apiClient.get<InterviewReportPage>(`${basePath}/reports`, {
        params: { current, size },
      }),
    ),
  get: (reportId: string) =>
    requestData(
      apiClient.get<InterviewReportResponse>(`${basePath}/reports/${reportId}`),
    ),
};
