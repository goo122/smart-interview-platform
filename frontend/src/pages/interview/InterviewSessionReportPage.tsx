import { Link, Navigate, useParams } from "react-router-dom";
import { ApiError, toUserMessage } from "@/api/errors";
import { useInterviewSession } from "@/features/interview/hooks";
import { useAutomaticReportGeneration, useSessionReport } from "@/features/report/hooks";
import { asReportStatus, type Report } from "@/features/report/types";
import { ReportStatusView } from "@/features/report/components/ReportStatusView";

export function InterviewSessionReportPage() {
  const { sessionId = "" } = useParams();
  const sessionQuery = useInterviewSession(sessionId);
  const reportQuery = useSessionReport(sessionId, Boolean(sessionId));
  const shouldGenerate = sessionQuery.data?.status === "COMPLETED";
  const generate = useAutomaticReportGeneration(sessionId, shouldGenerate, reportQuery);

  if (sessionQuery.isPending || reportQuery.isPending) return <div className="report-loading"><span className="spinner" />正在恢复报告状态…</div>;
  if (sessionQuery.isError || !sessionQuery.data) return <section className="report-not-found"><p className="eyebrow">SESSION NOT FOUND</p><h1>找不到这场面试</h1><p>{toUserMessage(sessionQuery.error)}</p><Link className="button button-primary" to="/interview">返回面试设置</Link></section>;
  if (sessionQuery.data.status !== "COMPLETED") return <section className="report-not-found"><p className="eyebrow">INTERVIEW INCOMPLETE</p><h1>面试尚未完成</h1><p>完成面试后才能生成报告。</p><Link className="button button-primary" to={`/interview/${sessionId}`}>返回面试</Link></section>;
  if (reportQuery.data) {
    const report = { ...reportQuery.data, status: asReportStatus(reportQuery.data.status) } as Report;
    if (report.status === "READY") return <Navigate to={`/interview/reports/${report.reportId}`} replace />;
    return <ReportStatusView status={report.status} message={report.failureMessage} onRetry={() => generate.mutate(sessionId)} retrying={generate.isPending} />;
  }
  if (reportQuery.isError && !(reportQuery.error instanceof ApiError && reportQuery.error.status === 404)) return <section className="report-not-found"><p className="eyebrow">REPORT ERROR</p><h1>报告状态暂时不可用</h1><p>{toUserMessage(reportQuery.error)}</p><button className="button button-secondary" type="button" onClick={() => reportQuery.refetch()}>重试</button></section>;
  return <ReportStatusView status={generate.isError ? "FAILED" : "PENDING"} message={generate.isError ? toUserMessage(generate.error) : null} onRetry={() => generate.mutate(sessionId)} retrying={generate.isPending} />;
}
