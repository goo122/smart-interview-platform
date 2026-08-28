import { apiClient, requestData } from "@/api/client";
import type {
  CreateInterviewSessionRequest,
  InterviewQuestionResponse,
  InterviewSessionPage,
  InterviewSessionResponse,
  InterviewTurnResponse,
  SubmitInterviewAnswerRequest,
  SubmitInterviewAnswerResponse,
} from "@/api/generated";

const basePath = "/xunzhi/v1/interview";

export const interviewApi = {
  listSessions: (current = 1, size = 20) =>
    requestData(apiClient.get<InterviewSessionPage>(`${basePath}/sessions`, { params: { current, size } })),
  createSession: (payload: CreateInterviewSessionRequest) =>
    requestData(apiClient.post<InterviewSessionResponse>(`${basePath}/sessions`, payload)),
  getSession: (sessionId: string) =>
    requestData(apiClient.get<InterviewSessionResponse>(`${basePath}/sessions/${sessionId}`)),
  getQuestions: (sessionId: string) =>
    requestData(apiClient.get<InterviewQuestionResponse[]>(`${basePath}/sessions/${sessionId}/questions`)),
  startSession: (sessionId: string) =>
    requestData(apiClient.post<InterviewSessionResponse>(`${basePath}/sessions/${sessionId}/start`)),
  cancelSession: (sessionId: string) =>
    requestData(apiClient.post<InterviewSessionResponse>(`${basePath}/sessions/${sessionId}/cancel`)),
  getCurrentTurn: (sessionId: string) =>
    requestData(apiClient.get<InterviewTurnResponse>(`${basePath}/sessions/${sessionId}/current-turn`)),
  submitAnswer: (sessionId: string, payload: SubmitInterviewAnswerRequest) =>
    requestData(apiClient.post<SubmitInterviewAnswerResponse>(`${basePath}/sessions/${sessionId}/answers`, payload)),
  listTurns: (sessionId: string) =>
    requestData(apiClient.get<InterviewTurnResponse[]>(`${basePath}/sessions/${sessionId}/turns`)),
  getTurn: (sessionId: string, turnId: string) =>
    requestData(apiClient.get<InterviewTurnResponse>(`${basePath}/sessions/${sessionId}/turns/${turnId}`)),
};

