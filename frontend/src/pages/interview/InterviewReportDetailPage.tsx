import { lazy, Suspense } from "react";
import { Link, useParams } from "react-router-dom";
import { toUserMessage } from "@/api/errors";
import { useReport, useReportGeneration } from "@/features/report/hooks";
import { asReportStatus, type Report } from "@/features/report/types";
import { ReportStatusView } from "@/features/report/components/ReportStatusView";

const ReportDocument = lazy(() => import("@/features/report/components/ReportDocument").then((module) => ({ default: module.ReportDocument })));

export function InterviewReportDetailPage() {
  const { reportId = "" } = useParams();
  const reportQuery = useReport(reportId);
  const generate = useReportGeneration();
  if (reportQuery.isPending) return <div className="report-loading"><span className="spinner" />正在恢复报告…</div>;
  if (reportQuery.isError || !reportQuery.data) return <section className="report-not-found"><p className="eyebrow">REPORT NOT FOUND</p><h1>找不到这份报告</h1><p>{toUserMessage(reportQuery.error)}</p><Link className="button button-primary" to="/interview/reports">返回报告列表</Link></section>;
  const report = { ...reportQuery.data, status: asReportStatus(reportQuery.data.status) } as Report;
  if (report.status !== "READY") return <ReportStatusView status={report.status} message={report.failureMessage} onRetry={report.status === "FAILED" ? () => generate.mutate(report.sessionId) : undefined} retrying={generate.isPending} />;
  return <Suspense fallback={<div className="report-loading"><span className="spinner" />正在加载报告详情…</div>}><ReportDocument report={report} /></Suspense>;
}
