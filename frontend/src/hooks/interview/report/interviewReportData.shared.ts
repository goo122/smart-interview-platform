import {
  interviewService,
  type InterviewRadarChartResult,
  type InterviewRecordResult,
  type InterviewReviewFeedbackResult,
} from "@/services/interviewService";
import type {
  QaReview,
  RadarPoint,
  ReviewFeedback,
} from "@/components/interview/report/types";

type UnknownRecord = Record<string, unknown>;

export type ReportQueryData = {
  record: InterviewRecordResult | null;
};

export type InterviewReportViewModel = {
  resumeScore: number | null;
  interviewScore: number | null;
  compositeScore: number | null;
  isCompositeEstimated: boolean;
  radarPoints: RadarPoint[];
  sortedSuggestions: string[];
  interviewDirection: string | null;
  qaReviews: QaReview[];
  reviewFeedback: ReviewFeedback;
};

const toRecord = (value: unknown): UnknownRecord | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as UnknownRecord;
};

const toNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const toBoolean = (value: unknown): boolean | null => {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y"].includes(normalized)) return true;
    if (["0", "false", "no", "n"].includes(normalized)) return false;
  }
  return null;
};

const normalizeScore = (value: unknown): number | null => {
  const parsed = toNumber(value);
  if (parsed === null) return null;
  return Math.max(0, Math.min(100, Math.round(parsed)));
};

const pickFirstString = (...values: unknown[]): string | null => {
  for (const value of values) {
    if (typeof value === "string" && value.trim() !== "") {
      return value.trim();
    }
  }
  return null;
};

const pickFirstNumber = (...values: unknown[]): number | null => {
  for (const value of values) {
    const parsed = normalizeScore(value);
    if (parsed !== null) return parsed;
  }
  return null;
};

const toStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0);
};

const parseJsonRecord = (value: unknown): UnknownRecord | null => {
  if (typeof value !== "string" || value.trim() === "") return null;
  try {
    return toRecord(JSON.parse(value));
  } catch (error) {
    console.warn(
      "[useInterviewReportData] failed to parse snapshot json",
      error,
    );
    return null;
  }
};

const parseRadarPoint = (value: unknown): RadarPoint | null => {
  const payload = toRecord(value);
  if (!payload) return null;

  const label = pickFirstString(
    payload.label,
    payload.name,
    payload.dimension,
    payload.metric,
  );
  const score = pickFirstNumber(
    payload.value,
    payload.score,
    payload.percent,
    payload.percentage,
  );

  if (!label || score === null) return null;
  return { label, value: score };
};

const extractRadarPoints = (record: UnknownRecord | null): RadarPoint[] => {
  if (!record) return [];

  const candidateArrayKeys = [
    "radarDimensions",
    "radarMetrics",
    "radarPoints",
    "abilityRadar",
    "radar",
    "abilityScores",
  ];

  for (const key of candidateArrayKeys) {
    const raw = record[key];
    if (!Array.isArray(raw)) continue;

    const parsed = raw
      .map(parseRadarPoint)
      .filter((item): item is RadarPoint => Boolean(item));
    if (parsed.length > 0) {
      return parsed.slice(0, 8);
    }
  }

  const candidateObjectKeys = [
    "abilityRadar",
    "radarMap",
    "abilityScoreMap",
    "radarScores",
  ];

  for (const key of candidateObjectKeys) {
    const raw = toRecord(record[key]);
    if (!raw) continue;

    const parsed = Object.entries(raw)
      .map(([label, value]) => {
        const score = pickFirstNumber(value);
        if (score === null || !label.trim()) return null;
        return { label: label.trim(), value: score };
      })
      .filter((item): item is RadarPoint => Boolean(item));

    if (parsed.length > 0) {
      return parsed.slice(0, 8);
    }
  }

  return [];
};

const buildRadarPointsFromDto = (
  radar: InterviewRadarChartResult | null,
): RadarPoint[] => {
  if (!radar) return [];

  const metrics: Array<[string, unknown]> = [
    ["简历评估", radar.resumeScore],
    ["面试表现", radar.interviewPerformance ?? radar.interviewScore],
    ["仪态表达", radar.demeanorEvaluation],
    ["专业技能", radar.professionalSkills],
    ["发展潜力", radar.potentialIndex ?? radar.totalScore],
  ];

  return metrics
    .map(([label, value]) => {
      const score = pickFirstNumber(value);
      return score === null ? null : { label, value: score };
    })
    .filter((item): item is RadarPoint => Boolean(item));
};

const pickFirstNonEmptyRadarPoints = (...groups: RadarPoint[][]) => {
  for (const group of groups) {
    if (group.length > 0) {
      return group;
    }
  }
  return [];
};

const parseQaReview = (value: unknown): QaReview | null => {
  const payload = toRecord(value);
  if (!payload) return null;

  const seq = toNumber(payload.seq);
  const questionNumber = pickFirstString(
    payload.questionNumber,
    payload.question_number,
  );
  const question = pickFirstString(
    payload.question,
    payload.q,
    payload.questionContent,
    payload.title,
  );
  const answer = pickFirstString(
    payload.answer,
    payload.a,
    payload.answerContent,
    payload.response,
  );
  const score = pickFirstNumber(payload.score, payload.interviewScore);
  const feedback = pickFirstString(
    payload.feedback,
    payload.scoreComment,
    payload.score_comment,
    payload.comment,
  );
  const isFollowUp = toBoolean(payload.isFollowUp ?? payload.is_follow_up);
  const followUpNeeded = toBoolean(
    payload.followUpNeeded ?? payload.follow_up_needed,
  );
  const followUpCount = pickFirstNumber(
    payload.followUpCount,
    payload.follow_up_count,
  );

  if (!question && !answer) return null;
  return {
    question: question || "题目内容缺失",
    answer: answer || "回答内容缺失",
    score,
    ...(feedback ? { feedback } : {}),
    ...(seq !== null ? { seq } : {}),
    ...(questionNumber ? { questionNumber } : {}),
    ...(isFollowUp !== null ? { isFollowUp } : {}),
    ...(followUpNeeded !== null ? { followUpNeeded } : {}),
    ...(followUpCount !== null ? { followUpCount } : {}),
  };
};

const extractQaReviews = (record: UnknownRecord | null): QaReview[] => {
  if (!record) return [];

  const candidateKeys = [
    "qaReviews",
    "questionAnswers",
    "interviewQaList",
    "qaList",
    "qas",
    "questionAnswerReviews",
    "playbackItems",
    "turns",
  ];

  for (const key of candidateKeys) {
    const raw = record[key];
    if (!Array.isArray(raw)) continue;

    const parsed = raw
      .map(parseQaReview)
      .filter((item): item is QaReview => Boolean(item));
    if (parsed.length > 0) {
      return parsed;
    }
  }

  return [];
};

const extractSuggestions = (
  record: InterviewRecordResult | null,
  rawRecord: UnknownRecord | null,
  snapshot: UnknownRecord | null,
) => {
  if (record?.interviewSuggestionsMap) {
    return Object.entries(record.interviewSuggestionsMap)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([, value]) => value)
      .filter((value) => value.trim().length > 0);
  }

  const rawText =
    pickFirstString(
      record?.interviewSuggestions,
      rawRecord?.interviewSuggestions,
      snapshot?.interviewSuggestions,
    ) || "";
  if (!rawText) return [];

  return rawText
    .split(/\r?\n|;|；/u)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
};

const mergeQaReviews = (...groups: QaReview[][]) => {
  const merged: QaReview[] = [];
  const seen = new Set<string>();

  groups.forEach((group) => {
    group.forEach((item) => {
      const key = `${item.questionNumber || ""}__${item.question}__${item.answer}__${item.followUpCount ?? ""}`;
      if (seen.has(key)) return;
      seen.add(key);
      merged.push(item);
    });
  });

  return merged;
};

const normalizeReviewFeedback = (value: unknown): ReviewFeedback | null => {
  const payload = toRecord(value);
  if (!payload) return null;

  const overallComment = pickFirstString(
    payload.overallComment,
    payload.summary,
    payload.comment,
  );
  const highlights = toStringArray(payload.highlights);
  const improvementTips = toStringArray(
    payload.improvementTips ?? payload.improvements,
  );
  const nextActions = toStringArray(
    payload.nextActions ?? payload.actions ?? payload.suggestions,
  );

  if (
    !overallComment &&
    highlights.length === 0 &&
    improvementTips.length === 0 &&
    nextActions.length === 0
  ) {
    return null;
  }

  return {
    overallComment,
    highlights,
    improvementTips,
    nextActions,
  };
};

const extractReviewFeedback = (
  record: InterviewRecordResult | null,
  rawRecord: UnknownRecord | null,
  snapshot: UnknownRecord | null,
  sortedSuggestions: string[],
): ReviewFeedback => {
  const parsed =
    normalizeReviewFeedback(record?.reviewFeedback) ??
    normalizeReviewFeedback(
      rawRecord?.reviewFeedback as InterviewReviewFeedbackResult | undefined,
    ) ??
    normalizeReviewFeedback(snapshot?.reviewFeedback);

  if (parsed) {
    return {
      overallComment: parsed.overallComment,
      highlights: parsed.highlights.slice(0, 3),
      improvementTips: parsed.improvementTips.slice(0, 3),
      nextActions: parsed.nextActions.slice(0, 3),
    };
  }

  return {
    overallComment: null,
    highlights: [],
    improvementTips: [],
    nextActions: sortedSuggestions.slice(0, 3),
  };
};

export async function fetchInterviewReportQueryData(
  sessionId: string,
): Promise<ReportQueryData> {
  try {
    const record =
      await interviewService.getInterviewRecordBySessionId(sessionId);
    return { record };
  } catch {
    try {
      await interviewService.saveInterviewRecord({ sessionId });
    } catch (manualSaveError) {
      console.warn(
        "[useInterviewReportData] manual save failed, fallback save-from-redis",
        manualSaveError,
      );
      await interviewService.saveInterviewRecordFromRedis(sessionId);
    }

    const record =
      await interviewService.getInterviewRecordBySessionId(sessionId);
    return { record };
  }
}

export function buildInterviewReportViewModel(
  record: InterviewRecordResult | null,
): InterviewReportViewModel {
  const rawRecord = toRecord(record);
  const snapshot = parseJsonRecord(
    pickFirstString(
      record?.sessionSnapshotJson,
      rawRecord?.sessionSnapshotJson,
    ),
  );

  const radarPoints = (() => {
    const fromRecordChartPayload = extractRadarPoints(
      toRecord(
        (record?.radarChart as InterviewRadarChartResult | null | undefined) ??
          null,
      ),
    );
    const fromRecordChart = buildRadarPointsFromDto(
      (record?.radarChart as InterviewRadarChartResult | null | undefined) ??
        null,
    );
    const fromRecord = extractRadarPoints(rawRecord);
    const fromSnapshot = extractRadarPoints(snapshot);
    const fallbackCandidates = [
      fromRecordChart,
      fromRecordChartPayload,
      fromRecord,
      fromSnapshot,
    ];
    return pickFirstNonEmptyRadarPoints(...fallbackCandidates);
  })();

  const qaReviews = mergeQaReviews(
    extractQaReviews(rawRecord),
    extractQaReviews(snapshot),
  );

  const sortedSuggestions = extractSuggestions(record, rawRecord, snapshot);

  const resumeScore = pickFirstNumber(
    record?.resumeScore,
    rawRecord?.resumeScore,
    snapshot?.resumeScore,
  );

  const interviewScore = pickFirstNumber(
    record?.interviewScore,
    rawRecord?.interviewScore,
    rawRecord?.interviewPerformance,
    snapshot?.interviewScore,
    snapshot?.interviewPerformance,
  );

  const rawCompositeScore = pickFirstNumber(
    record?.compositeScore,
    record?.totalScore,
    record?.finalScore,
    rawRecord?.compositeScore,
    rawRecord?.totalScore,
    rawRecord?.finalScore,
    snapshot?.compositeScore,
    snapshot?.totalScore,
    snapshot?.finalScore,
    snapshot?.potentialIndex,
  );

  const compositeScore =
    rawCompositeScore ??
    (() => {
      const available = [resumeScore, interviewScore].filter(
        (item): item is number => item !== null,
      );
      if (available.length === 0) return null;
      const avg =
        available.reduce((sum, item) => sum + item, 0) / available.length;
      return normalizeScore(avg);
    })();

  const isCompositeEstimated =
    rawCompositeScore === null &&
    compositeScore !== null &&
    (resumeScore !== null || interviewScore !== null);

  const interviewDirection = pickFirstString(
    record?.interviewDirection,
    rawRecord?.interviewDirection,
    rawRecord?.interviewType,
    rawRecord?.direction,
    snapshot?.interviewDirection,
  );

  const reviewFeedback = extractReviewFeedback(
    record,
    rawRecord,
    snapshot,
    sortedSuggestions,
  );

  return {
    resumeScore,
    interviewScore,
    compositeScore,
    isCompositeEstimated,
    radarPoints,
    sortedSuggestions,
    interviewDirection,
    qaReviews,
    reviewFeedback,
  };
}
