const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "") || "/";

export const frontendEnv = {
  apiBaseUrl: trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || "/api"),
  apiTarget: import.meta.env.VITE_API_TARGET || "http://localhost:8000",
  knowledgeMaxFileSizeBytes: Number(import.meta.env.VITE_KNOWLEDGE_MAX_FILE_SIZE_BYTES || 20 * 1024 * 1024),
  interviewMinAnswerLength: Number(import.meta.env.VITE_INTERVIEW_MIN_ANSWER_LENGTH || 10),
  interviewMaxAnswerLength: Number(import.meta.env.VITE_INTERVIEW_MAX_ANSWER_LENGTH || 10000),
} as const;
