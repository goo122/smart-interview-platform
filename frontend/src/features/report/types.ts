import type {
  InterviewReportItemResponse,
  InterviewReportPage,
  InterviewReportResponse,
} from "@/api/generated";

export type ReportStatus = "PENDING" | "GENERATING" | "READY" | "FAILED";
export type GeneratedBy = "RULES" | "LLM" | "HYBRID";
export type ReportDimension = "technical" | "relevance" | "clarity" | "depth";

export type Report = InterviewReportResponse & { status: ReportStatus };
export type ReportItem = InterviewReportItemResponse;
export type ReportPage = InterviewReportPage;

export const reportStatusLabels: Record<ReportStatus, string> = {
  PENDING: "等待生成",
  GENERATING: "正在生成",
  READY: "已完成",
  FAILED: "生成失败",
};

export const generatedByLabels: Record<GeneratedBy, string> = {
  RULES: "规则生成",
  LLM: "AI 生成",
  HYBRID: "确定性评分 + AI 建议",
};

export const dimensionLabels: Record<ReportDimension, string> = {
  technical: "技术能力",
  relevance: "岗位相关性",
  clarity: "表达清晰度",
  depth: "回答深度",
};

export const reportDimensions: readonly ReportDimension[] = [
  "technical",
  "relevance",
  "clarity",
  "depth",
];

export function asReportStatus(value: string): ReportStatus {
  if (value === "GENERATING" || value === "READY" || value === "FAILED") return value;
  return "PENDING";
}

export function asGeneratedBy(value: string): GeneratedBy {
  if (value === "LLM" || value === "HYBRID") return value;
  return "RULES";
}

export function safeScore(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 100) {
    return null;
  }
  return value;
}

export function reportScore(report: Report, dimension: ReportDimension): number | null {
  return safeScore(report.dimensionScores[dimension]);
}

export function itemScore(item: ReportItem, dimension: "overall" | ReportDimension): number | null {
  return safeScore(item.scores[dimension]);
}

export function radarScore(report: Report, dimension: ReportDimension): number | null {
  const radarPoint = report.radarData.find(
    (point) => point["dimension"] === dimension,
  );
  return safeScore(radarPoint?.["score"]) ?? reportScore(report, dimension);
}

export function formatReportDate(value: string | null | undefined): string {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function sourceText(source: Record<string, unknown>, key: string): string | null {
  const value = source[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function sourcePage(source: Record<string, unknown>): number | null {
  const value = source["pageNumber"];
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
}
