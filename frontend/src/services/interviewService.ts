import service, { assertRequestAuthorized, buildApiUrl } from "@/lib/request";
import { AppError, ErrorCode } from "@/lib/errors";
import type { AxiosRequestConfig } from "axios";

const INTERVIEW_LONG_TIMEOUT_MS = 180000;

export interface UploadResumeParams {
  agentId: number;
  file: File;
  sessionId?: string;
  bizType?: string;
}

export interface UploadResumeResult {
  id: number;
  agentId: number;
  sessionId?: string | null;
  bizType: string;
  fileName: string;
  fileSize: number;
  contentType?: string | null;
  fileUrl: string;
  createTime: string;
}

export interface ExtractInterviewQuestionsParams {
  sessionId: string;
  resumePdf: File;
}

export interface CreateInterviewSessionResult {
  sessionId: string;
  status?: string | null;
}

export interface ExtractInterviewQuestionsResult {
  id?: string;
  sessionId?: string;
  userName?: string;
  agentId?: number;
  questions?: Record<string, string>;
  suggestions?: Record<string, string>;
  interviewType?: string;
  resumeFileUrl?: string;
  responseTime?: number;
  tokenCount?: number;
  resumeScore?: number;
  questionCount?: number;
  suggestionCount?: number;
  isSuccess?: number;
  errorMessage?: string;
  createTime?: string;
  updateTime?: string;
}

export interface InterviewRecordResult {
  id: number;
  userId: number;
  sessionId: string;
  resumeScore?: number | null;
  interviewScore?: number | null;
  interviewStatus?: string | null;
  questionCount?: number | null;
  compositeScore?: number | null;
  totalScore?: number | null;
  finalScore?: number | null;
  interviewSuggestions?: string | null;
  interviewSuggestionsMap?: Record<string, string> | null;
  interviewDirection?: string | null;
  sessionSnapshotJson?: string | null;
  radarChart?: InterviewRadarChartResult | null;
  radarDimensions?: InterviewRadarMetric[] | null;
  radarMetrics?: InterviewRadarMetric[] | null;
  radarPoints?: InterviewRadarMetric[] | null;
  playbackItems?: InterviewQaReview[] | null;
  qaReviews?: InterviewQaReview[] | null;
  questionAnswers?: InterviewQaReview[] | null;
  interviewQaList?: InterviewQaReview[] | null;
  reviewFeedback?: InterviewReviewFeedbackResult | null;
  startTime?: string | null;
  endTime?: string | null;
  durationSeconds?: number | null;
  createTime?: string;
  updateTime?: string;
}

export interface InterviewReviewFeedbackResult {
  overallComment?: string | null;
  highlights?: string[] | null;
  improvementTips?: string[] | null;
  nextActions?: string[] | null;
}

export interface InterviewRecordsPageResult {
  records: InterviewRecordResult[];
  total: number;
  size: number;
  current: number;
  pages: number;
}

export interface InterviewRadarMetric {
  label?: string | null;
  value?: number | string | null;
}

export interface InterviewQaReview {
  seq?: number | null;
  questionNumber?: string | null;
  question?: string | null;
  answer?: string | null;
  score?: number | string | null;
  feedback?: string | null;
  isFollowUp?: boolean | null;
  followUpNeeded?: boolean | null;
  followUpCount?: number | string | null;
}

export interface InterviewRadarChartResult {
  resumeScore?: number | null;
  interviewPerformance?: number | null;
  demeanorEvaluation?: number | null;
  professionalSkills?: number | null;
  potentialIndex?: number | null;
  radarMetrics?: InterviewRadarMetric[] | null;
  radarPoints?: InterviewRadarMetric[] | null;
  interviewScore?: number | null;
  totalScore?: number | null;
  [key: string]: unknown;
}

export interface PageInterviewRecordsParams {
  pageNum: number;
  pageSize: number;
  sessionId?: string;
  minScore?: number;
  maxScore?: number;
  interviewDirection?: string;
}

export interface PageInterviewConversationsParams {
  current?: number;
  size?: number;
  status?: string;
  keyword?: string;
}

export interface InterviewConversationItem {
  sessionId: string;
  conversationTitle?: string | null;
  status?: string | null;
  interviewType?: string | null;
  resumeFileUrl?: string | null;
  createTime?: string | null;
  updateTime?: string | null;
}

export interface InterviewConversationsPageResult {
  records: InterviewConversationItem[];
  total?: number;
  size?: number;
  current?: number;
  pages?: number;
}

export interface InterviewSessionRestoreResult {
  sessionId?: string | null;
  status?: string | null;
  canResume?: boolean | null;
  resumeFileUrl?: string | null;
  resumeScore?: number | null;
  interviewType?: string | null;
  suggestions?: Record<string, string> | null;
}

export interface AnswerInterviewQuestionParams {
  sessionId: string;
  questionNumber: string;
  answerContent?: string;
  audioFile?: File;
  requestId?: string;
}

export interface EvaluateInterviewDemeanorParams {
  sessionId: string;
  userPhoto: Blob;
  fileName?: string;
}

export interface AnswerInterviewQuestionResult {
  questionNumber?: string;
  questionContent?: string;
  score?: number;
  totalScore?: number;
  isSuccess?: boolean;
  errorMessage?: string;
  feedback?: string;
  nextQuestion?: string | null;
  nextQuestionNumber?: string | null;
  isFollowUp?: boolean;
  followUpNeeded?: boolean;
  followUpCount?: number;
  askToUser?: string | null;
  missingPoints?: string[] | Record<string, string>;
  finished?: boolean;
}

type AnswerInterviewQuestionJsonPayload = {
  questionNumber: string;
  answerContent?: string;
  requestId?: string;
};

type UnknownRecord = Record<string, unknown>;

const toRecord = (value: unknown): UnknownRecord =>
  value && typeof value === "object" ? (value as UnknownRecord) : {};

const pickFirst = (source: UnknownRecord, keys: string[]) => {
  for (const key of keys) {
    const value = source[key];
    if (value !== undefined && value !== null) {
      return value;
    }
  }
  return undefined;
};

const toStringValue = (value: unknown): string | undefined => {
  if (typeof value === "string") {
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : undefined;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return undefined;
};

const toNullableString = (value: unknown): string | null | undefined => {
  if (value === null) return null;
  return toStringValue(value);
};

const toNumberValue = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const toBooleanValue = (value: unknown): boolean | undefined => {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y"].includes(normalized)) {
      return true;
    }
    if (["0", "false", "no", "n"].includes(normalized)) {
      return false;
    }
  }
  return undefined;
};

const toStringMap = (value: unknown): Record<string, string> | undefined => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  const source = value as Record<string, unknown>;
  const mapped: Record<string, string> = {};
  Object.entries(source).forEach(([key, entry]) => {
    const normalized = toStringValue(entry);
    if (normalized) {
      mapped[key] = normalized;
    }
  });
  return Object.keys(mapped).length > 0 ? mapped : undefined;
};

const toMissingPoints = (
  value: unknown,
): AnswerInterviewQuestionResult["missingPoints"] => {
  if (Array.isArray(value)) {
    const points = value
      .map((item) => toStringValue(item))
      .filter((item): item is string => Boolean(item));
    return points.length > 0 ? points : undefined;
  }
  const mapped = toStringMap(value);
  if (mapped) {
    return mapped;
  }
  const single = toStringValue(value);
  return single ? [single] : undefined;
};

const normalizeExtractInterviewQuestions = (
  payload: ExtractInterviewQuestionsResult,
): ExtractInterviewQuestionsResult => {
  const source = toRecord(payload);
  const success =
    toBooleanValue(pickFirst(source, ["isSuccess", "is_success", "success"])) ??
    true;

  return {
    ...payload,
    id: toStringValue(pickFirst(source, ["id"])) ?? payload.id,
    sessionId:
      toStringValue(pickFirst(source, ["sessionId", "session_id"])) ??
      payload.sessionId,
    userName:
      toStringValue(pickFirst(source, ["userName", "user_name", "username"])) ??
      payload.userName,
    agentId:
      toNumberValue(pickFirst(source, ["agentId", "agent_id"])) ??
      payload.agentId,
    questions:
      toStringMap(
        pickFirst(source, ["questions", "questionMap", "question_map"]),
      ) ?? payload.questions,
    suggestions:
      toStringMap(
        pickFirst(source, [
          "suggestions",
          "missingPoints",
          "missing_points",
          "interviewSuggestionsMap",
          "interview_suggestions_map",
        ]),
      ) ?? payload.suggestions,
    interviewType:
      toStringValue(
        pickFirst(source, ["interviewType", "interview_type", "type"]),
      ) ?? payload.interviewType,
    resumeFileUrl:
      toStringValue(
        pickFirst(source, ["resumeFileUrl", "resume_file_url", "resumeUrl"]),
      ) ?? payload.resumeFileUrl,
    responseTime:
      toNumberValue(pickFirst(source, ["responseTime", "response_time"])) ??
      payload.responseTime,
    tokenCount:
      toNumberValue(pickFirst(source, ["tokenCount", "token_count"])) ??
      payload.tokenCount,
    resumeScore:
      toNumberValue(pickFirst(source, ["resumeScore", "resume_score"])) ??
      payload.resumeScore,
    questionCount:
      toNumberValue(pickFirst(source, ["questionCount", "question_count"])) ??
      payload.questionCount,
    suggestionCount:
      toNumberValue(
        pickFirst(source, ["suggestionCount", "suggestion_count"]),
      ) ?? payload.suggestionCount,
    isSuccess: success ? 1 : 0,
    errorMessage:
      toStringValue(
        pickFirst(source, ["errorMessage", "error_message", "message"]),
      ) ?? payload.errorMessage,
    createTime:
      toStringValue(pickFirst(source, ["createTime", "create_time"])) ??
      payload.createTime,
    updateTime:
      toStringValue(pickFirst(source, ["updateTime", "update_time"])) ??
      payload.updateTime,
  };
};

export const normalizeInterviewAnswer = (
  payload: AnswerInterviewQuestionResult,
): AnswerInterviewQuestionResult => {
  const source = toRecord(payload);
  const isSuccess =
    toBooleanValue(pickFirst(source, ["isSuccess", "is_success", "success"])) ??
    true;
  const isFollowUp =
    toBooleanValue(pickFirst(source, ["isFollowUp", "is_follow_up"])) ?? false;
  const followUpNeeded =
    toBooleanValue(pickFirst(source, ["followUpNeeded", "follow_up_needed"])) ??
    payload.followUpNeeded;
  const finished =
    toBooleanValue(
      pickFirst(source, [
        "finished",
        "isFinished",
        "is_finished",
        "interviewFinished",
        "interview_finished",
        "done",
      ]),
    ) ?? false;
  const askToUser = toNullableString(
    pickFirst(source, ["askToUser", "ask_to_user"]),
  );
  const nextQuestion =
    toNullableString(
      pickFirst(source, [
        "nextQuestion",
        "next_question",
        "followUpQuestion",
        "follow_up_question",
      ]),
    ) ??
    askToUser ??
    payload.nextQuestion;

  return {
    ...payload,
    questionNumber:
      toStringValue(pickFirst(source, ["questionNumber", "question_number"])) ??
      payload.questionNumber,
    questionContent:
      toStringValue(
        pickFirst(source, ["questionContent", "question_content"]),
      ) ?? payload.questionContent,
    score: toNumberValue(pickFirst(source, ["score"])) ?? payload.score,
    totalScore:
      toNumberValue(
        pickFirst(source, ["totalScore", "total_score", "interviewScore"]),
      ) ?? payload.totalScore,
    isSuccess,
    errorMessage:
      toStringValue(
        pickFirst(source, ["errorMessage", "error_message", "message"]),
      ) ?? payload.errorMessage,
    feedback:
      toStringValue(
        pickFirst(source, ["feedback", "scoreComment", "score_comment"]),
      ) ?? payload.feedback,
    nextQuestion,
    nextQuestionNumber:
      toNullableString(
        pickFirst(source, ["nextQuestionNumber", "next_question_number"]),
      ) ?? payload.nextQuestionNumber,
    isFollowUp,
    followUpNeeded,
    followUpCount:
      toNumberValue(pickFirst(source, ["followUpCount", "follow_up_count"])) ??
      payload.followUpCount,
    askToUser: askToUser ?? payload.askToUser,
    missingPoints:
      toMissingPoints(pickFirst(source, ["missingPoints", "missing_points"])) ??
      payload.missingPoints,
    finished,
  };
};

const normalizeInterviewRadarChart = (
  payload: InterviewRadarChartResult,
): InterviewRadarChartResult => {
  const source = toRecord(payload);

  const normalizeMetrics = (
    value: unknown,
  ): InterviewRadarMetric[] | undefined => {
    if (!Array.isArray(value)) return undefined;
    const mapped = value
      .map((item): InterviewRadarMetric | null => {
        const row = toRecord(item);
        const label = toStringValue(
          pickFirst(row, ["label", "name", "dimension", "metric"]),
        );
        const rawValue = pickFirst(row, [
          "value",
          "score",
          "percent",
          "percentage",
        ]);
        const parsedValue =
          typeof rawValue === "number" || typeof rawValue === "string"
            ? rawValue
            : undefined;
        if (!label || parsedValue === undefined) return null;
        return { label, value: parsedValue };
      })
      .filter((item): item is InterviewRadarMetric => item !== null);
    return mapped.length > 0 ? mapped : undefined;
  };

  return {
    ...payload,
    resumeScore:
      toNumberValue(pickFirst(source, ["resumeScore", "resume_score"])) ??
      payload.resumeScore,
    interviewPerformance:
      toNumberValue(
        pickFirst(source, ["interviewPerformance", "interview_performance"]),
      ) ?? payload.interviewPerformance,
    demeanorEvaluation:
      toNumberValue(
        pickFirst(source, ["demeanorEvaluation", "demeanor_evaluation"]),
      ) ?? payload.demeanorEvaluation,
    professionalSkills:
      toNumberValue(
        pickFirst(source, ["professionalSkills", "professional_skills"]),
      ) ?? payload.professionalSkills,
    potentialIndex:
      toNumberValue(pickFirst(source, ["potentialIndex", "potential_index"])) ??
      payload.potentialIndex,
    radarMetrics:
      normalizeMetrics(
        pickFirst(source, ["radarMetrics", "radar_metrics", "abilityRadar"]),
      ) ??
      (Array.isArray(payload.radarMetrics) ? payload.radarMetrics : undefined),
    radarPoints:
      normalizeMetrics(
        pickFirst(source, [
          "radarPoints",
          "radar_points",
          "radar",
          "abilityScores",
        ]),
      ) ??
      (Array.isArray(payload.radarPoints) ? payload.radarPoints : undefined),
    interviewScore:
      toNumberValue(pickFirst(source, ["interviewScore", "interview_score"])) ??
      payload.interviewScore,
    totalScore:
      toNumberValue(pickFirst(source, ["totalScore", "total_score"])) ??
      payload.totalScore,
  };
};

const normalizeInterviewConversationsPage = (
  payload: InterviewConversationsPageResult,
): InterviewConversationsPageResult => {
  const source = toRecord(payload);
  const records = Array.isArray(source.records) ? source.records : [];
  const normalizedRecords: InterviewConversationItem[] = [];

  records.forEach((item) => {
    const row = toRecord(item);
    const sessionId = toStringValue(
      pickFirst(row, ["sessionId", "session_id"]),
    );
    if (!sessionId) return;

    normalizedRecords.push({
      sessionId,
      conversationTitle:
        toNullableString(
          pickFirst(row, ["conversationTitle", "conversation_title", "title"]),
        ) ?? null,
      status: toNullableString(pickFirst(row, ["status"])) ?? null,
      interviewType:
        toNullableString(
          pickFirst(row, ["interviewType", "interview_type", "type"]),
        ) ?? null,
      resumeFileUrl:
        toNullableString(
          pickFirst(row, ["resumeFileUrl", "resume_file_url", "resumeUrl"]),
        ) ?? null,
      createTime:
        toNullableString(pickFirst(row, ["createTime", "create_time"])) ?? null,
      updateTime:
        toNullableString(pickFirst(row, ["updateTime", "update_time"])) ?? null,
    });
  });

  return {
    records: normalizedRecords,
    total: toNumberValue(pickFirst(source, ["total"])) ?? payload.total,
    size: toNumberValue(pickFirst(source, ["size"])) ?? payload.size,
    current: toNumberValue(pickFirst(source, ["current"])) ?? payload.current,
    pages: toNumberValue(pickFirst(source, ["pages"])) ?? payload.pages,
  };
};

const normalizeInterviewSessionRestore = (
  payload: InterviewSessionRestoreResult,
): InterviewSessionRestoreResult => {
  const source = toRecord(payload);

  return {
    sessionId:
      toNullableString(pickFirst(source, ["sessionId", "session_id"])) ??
      payload.sessionId,
    status: toNullableString(pickFirst(source, ["status"])) ?? payload.status,
    canResume:
      toBooleanValue(pickFirst(source, ["canResume", "can_resume"])) ??
      payload.canResume,
    resumeFileUrl:
      toNullableString(
        pickFirst(source, ["resumeFileUrl", "resume_file_url", "resumeUrl"]),
      ) ?? payload.resumeFileUrl,
    resumeScore:
      toNumberValue(pickFirst(source, ["resumeScore", "resume_score"])) ??
      payload.resumeScore,
    interviewType:
      toNullableString(
        pickFirst(source, ["interviewType", "interview_type", "type"]),
      ) ?? payload.interviewType,
    suggestions:
      toStringMap(
        pickFirst(source, ["suggestions", "suggestionMap", "suggestion_map"]),
      ) ?? payload.suggestions,
  };
};

const shouldFallbackToLegacyPath = (error: unknown) => {
  if (!(error instanceof AppError)) return false;
  return (
    error.code === ErrorCode.RESOURCE_NOT_FOUND ||
    error.code === ErrorCode.OPERATION_FAILED
  );
};

const getWithPathFallback = async <T>(
  primaryPath: string,
  legacyPath: string,
) => {
  try {
    return await service.get<T>(primaryPath);
  } catch (error) {
    if (!shouldFallbackToLegacyPath(error)) {
      throw error;
    }
    return service.get<T>(legacyPath);
  }
};

const getWithPathFallbackAndConfig = async <T>(
  primaryPath: string,
  legacyPath: string,
  config?: AxiosRequestConfig,
) => {
  try {
    return await service.get<T>(primaryPath, config);
  } catch (error) {
    if (!shouldFallbackToLegacyPath(error)) {
      throw error;
    }
    return service.get<T>(legacyPath, config);
  }
};

const postWithPathFallback = async <T, D = unknown>(
  primaryPath: string,
  legacyPath: string,
  data?: D,
) => {
  try {
    return await service.post<T, D>(primaryPath, data);
  } catch (error) {
    if (!shouldFallbackToLegacyPath(error)) {
      throw error;
    }
    return service.post<T, D>(legacyPath, data);
  }
};

const normalizeRequiredQuestionNumber = (questionNumber: string): string => {
  const normalized = questionNumber?.trim();
  if (normalized) {
    return normalized;
  }
  throw new AppError(
    ErrorCode.CLIENT_VALIDATION_ERROR,
    "questionNumber is required for interview answer submission",
  );
};

const buildAnswerFormData = (params: AnswerInterviewQuestionParams) => {
  const formData = new FormData();
  formData.append(
    "questionNumber",
    normalizeRequiredQuestionNumber(params.questionNumber),
  );
  if (params.answerContent) {
    formData.append("answerContent", params.answerContent);
  }
  if (params.audioFile) {
    formData.append("audioFile", params.audioFile);
  }
  if (params.requestId) {
    formData.append("requestId", params.requestId);
  }
  return formData;
};

const buildResumePreviewPath = (sessionId: string) =>
  `/xunzhi/v1/interview/sessions/${encodeURIComponent(sessionId)}/resume/preview`;

const decodePreviewError = (bytes: Uint8Array) => {
  const previewBytes = bytes.slice(0, Math.min(bytes.length, 2048));
  const text = new TextDecoder("utf-8", { fatal: false }).decode(previewBytes);
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length > 0 ? normalized : undefined;
};

export const interviewService = {
  createInterviewSession: async () => {
    return service.post<CreateInterviewSessionResult, Record<string, never>>(
      "/xunzhi/v1/interview/sessions",
      {},
    );
  },
  pageInterviewConversations: async (
    params: PageInterviewConversationsParams,
  ) => {
    const response = await service.get<InterviewConversationsPageResult>(
      "/xunzhi/v1/interview/conversations",
      {
        params,
      },
    );
    return normalizeInterviewConversationsPage(response);
  },
  restoreInterviewSession: async (sessionId: string) => {
    const response = await service.get<InterviewSessionRestoreResult>(
      `/xunzhi/v1/interview/sessions/${encodeURIComponent(sessionId)}/restore`,
    );
    return normalizeInterviewSessionRestore(response);
  },
  fetchInterviewResumePreviewBlob: async (sessionId: string) => {
    const token = assertRequestAuthorized(buildResumePreviewPath(sessionId));
    const response = await fetch(
      buildApiUrl(buildResumePreviewPath(sessionId)),
      {
        method: "GET",
        credentials: "same-origin",
        headers: token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : undefined,
      },
    );

    if (!response.ok) {
      const errorMessage = (await response.text()).trim();
      throw new Error(
        errorMessage || `Failed to load resume preview (${response.status})`,
      );
    }

    const contentType =
      response.headers.get("content-type")?.toLowerCase() ?? "";
    const arrayBuffer = await response.arrayBuffer();
    const bytes = new Uint8Array(arrayBuffer);

    const isPdf =
      bytes.length >= 5 &&
      bytes[0] === 0x25 &&
      bytes[1] === 0x50 &&
      bytes[2] === 0x44 &&
      bytes[3] === 0x46 &&
      bytes[4] === 0x2d;
    if (!isPdf && !contentType.includes("pdf")) {
      throw new Error(
        decodePreviewError(bytes) ||
          `Resume preview returned unexpected content type: ${contentType || "unknown"}`,
      );
    }
    if (!isPdf) {
      throw new Error(
        decodePreviewError(bytes) || "Resume preview is not a valid PDF",
      );
    }

    const blob = new Blob([arrayBuffer], {
      type: "application/pdf",
    });
    if (blob.size === 0) {
      throw new Error("Failed to load resume preview: empty file");
    }
    return blob;
  },
  uploadResume: async (params: UploadResumeParams) => {
    const formData = new FormData();
    formData.append("agentId", String(params.agentId));
    if (params.sessionId) {
      formData.append("sessionId", params.sessionId);
    }
    formData.append("bizType", params.bizType || "resume");
    formData.append("file", params.file);

    return service.post<UploadResumeResult, FormData>(
      "/xunzhi/v1/agents/files/upload",
      formData,
      {
        timeout: INTERVIEW_LONG_TIMEOUT_MS,
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
  },
  extractInterviewQuestions: async (
    params: ExtractInterviewQuestionsParams,
  ) => {
    const formData = new FormData();
    formData.append("resumePdf", params.resumePdf);

    const response = await service.post<
      ExtractInterviewQuestionsResult,
      FormData
    >(
      `/xunzhi/v1/interview/sessions/${encodeURIComponent(params.sessionId)}/interview-questions`,
      formData,
      {
        timeout: INTERVIEW_LONG_TIMEOUT_MS,
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
    return normalizeExtractInterviewQuestions(response);
  },
  answerInterviewQuestion: async (params: AnswerInterviewQuestionParams) => {
    const questionNumber = normalizeRequiredQuestionNumber(
      params.questionNumber,
    );
    const answerRequestPolicy = {
      dedupe: "reject" as const,
      debounceMs: 250,
      key: `interview-answer:${params.sessionId}:${questionNumber}`,
    };
    if (!params.audioFile) {
      const payload: AnswerInterviewQuestionJsonPayload = {
        questionNumber,
        answerContent: params.answerContent,
        requestId: params.requestId,
      };
      try {
        const response = await service.post<
          AnswerInterviewQuestionResult,
          AnswerInterviewQuestionJsonPayload
        >(
          `/xunzhi/v1/interview/sessions/${encodeURIComponent(params.sessionId)}/interview/answer-json`,
          payload,
          {
            timeout: INTERVIEW_LONG_TIMEOUT_MS,
            requestPolicy: answerRequestPolicy,
          },
        );
        return normalizeInterviewAnswer(response);
      } catch (error) {
        console.warn(
          "[interviewService] answer-json failed, fallback to multipart /interview/answer",
          error,
        );
      }
    }

    const formData = buildAnswerFormData(params);
    const response = await service.post<
      AnswerInterviewQuestionResult,
      FormData
    >(
      `/xunzhi/v1/interview/sessions/${encodeURIComponent(params.sessionId)}/interview/answer`,
      formData,
      {
        timeout: INTERVIEW_LONG_TIMEOUT_MS,
        requestPolicy: answerRequestPolicy,
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
    return normalizeInterviewAnswer(response);
  },
  getNextQuestion: async (sessionId: string) => {
    const response = await service.get<AnswerInterviewQuestionResult>(
      `/xunzhi/v1/interview/sessions/${encodeURIComponent(sessionId)}/next-question`,
    );
    return normalizeInterviewAnswer(response);
  },
  getCurrentQuestion: async (sessionId: string) => {
    try {
      const response = await service.get<AnswerInterviewQuestionResult>(
        `/xunzhi/v1/interview/sessions/${encodeURIComponent(sessionId)}/current-question`,
      );
      return normalizeInterviewAnswer(response);
    } catch (error) {
      if (shouldFallbackToLegacyPath(error)) {
        return interviewService.getNextQuestion(sessionId);
      }
      throw error;
    }
  },
  evaluateInterviewDemeanor: async (
    params: EvaluateInterviewDemeanorParams,
  ) => {
    const formData = new FormData();
    formData.append(
      "userPhoto",
      params.userPhoto,
      params.fileName || `demeanor-${Date.now()}.jpg`,
    );

    return service.post<string, FormData>(
      `/xunzhi/v1/interview/sessions/${encodeURIComponent(params.sessionId)}/demeanor-evaluation`,
      formData,
      {
        timeout: INTERVIEW_LONG_TIMEOUT_MS,
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
  },
  finishInterviewSession: async (sessionId: string) => {
    return service.put<void, Record<string, never>>(
      `/xunzhi/v1/interview/sessions/${encodeURIComponent(sessionId)}/finish`,
      {},
    );
  },
  saveInterviewRecordFromRedis: async (sessionId: string) => {
    return postWithPathFallback<void>(
      `/xunzhi/v1/interview/interview/record/save-from-redis/${encodeURIComponent(sessionId)}`,
      `/xunzhi/v1/interview/record/save-from-redis/${encodeURIComponent(sessionId)}`,
    );
  },
  saveInterviewRecord: async (params: { sessionId: string }) => {
    return postWithPathFallback<void, { sessionId: string }>(
      "/xunzhi/v1/interview/interview/record",
      "/xunzhi/v1/interview/record",
      params,
    );
  },
  pageInterviewRecords: async (params: PageInterviewRecordsParams) => {
    return getWithPathFallbackAndConfig<InterviewRecordsPageResult>(
      "/xunzhi/v1/interview/interview/records",
      "/xunzhi/v1/interview/records",
      {
        params,
      },
    );
  },
  getInterviewRadarChart: async (sessionId: string) => {
    const response = await service.get<InterviewRadarChartResult>(
      `/xunzhi/v1/interview/sessions/${encodeURIComponent(sessionId)}/radar-chart`,
    );
    return normalizeInterviewRadarChart(response);
  },
  getInterviewRecordBySessionId: async (sessionId: string) => {
    return getWithPathFallback<InterviewRecordResult>(
      `/xunzhi/v1/interview/interview/record/${encodeURIComponent(sessionId)}`,
      `/xunzhi/v1/interview/record/${encodeURIComponent(sessionId)}`,
    );
  },
};
