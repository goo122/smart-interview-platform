import { Link, useSearchParams } from "react-router-dom";
import { toUserMessage } from "@/api/errors";
import { useReports } from "@/features/report/hooks";
import {
  asReportStatus,
  formatReportDate,
  reportStatusLabels,
  safeScore,
} from "@/features/report/types";

const pageSize = 10;

export function InterviewReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const parsedPage = Number.parseInt(searchParams.get("current") ?? "1", 10);
  const current = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const reportsQuery = useReports(current, pageSize);
  const page = reportsQuery.data;
  const records = page?.records ?? [];

  const setPage = (next: number) => {
    setSearchParams(next > 1 ? { current: String(next) } : {});
  };

  return (
    <section className="report-list-page">
      <header className="report-list-heading">
        <div><p className="eyebrow">YOUR PROGRESS</p><h1>面试报告</h1><p>回顾每一场练习，把反馈变成下一次进步。</p></div>
        <Link className="button button-primary" to="/interview">开始新面试</Link>
      </header>
      {reportsQuery.isPending ? <div className="report-loading"><span className="spinner" />正在加载报告…</div> : null}
      {reportsQuery.isError ? (
        <section className="report-inline-error" role="alert"><p>{toUserMessage(reportsQuery.error)}</p><button className="button button-secondary" type="button" onClick={() => reportsQuery.refetch()}>重试</button></section>
      ) : null}
      {!reportsQuery.isPending && !reportsQuery.isError && !records.length ? (
        <section className="report-empty-state"><p className="eyebrow">NO REPORTS YET</p><h2>完成一场面试后，报告会出现在这里</h2><p>上传简历并开始一次模拟面试，系统会为你保留评分、回放和改进建议。</p><Link className="button button-primary" to="/interview">去创建面试</Link></section>
      ) : null}
      {records.length ? <div className="report-list" aria-label="历史报告">{records.map((report) => {
        const status = asReportStatus(report.status);
        const score = status === "READY" ? safeScore(report.overallScore) : null;
        return <article className="report-list-item" key={report.reportId}>
          <div className="report-list-item-main"><span className={`report-status-pill ${status.toLowerCase()}`}>{reportStatusLabels[status]}</span><h2>{report.jobTitle}</h2><p>{report.interviewType} · {report.difficulty}</p></div>
          <div className="report-list-item-score">{score === null ? <span>—</span> : <><strong>{score}</strong><small>/ 100</small></>}</div>
          <div className="report-list-item-meta"><span>{formatReportDate(report.completedAt ?? report.updatedAt)}</span><span>{report.generatedBy || "生成方式未知"}</span></div>
          <Link className="button button-secondary" to={`/interview/reports/${report.reportId}`}>{status === "READY" ? "查看报告" : "查看状态"}</Link>
        </article>;
      })}</div> : null}
      {page && page.pages > 1 ? <nav className="report-pagination" aria-label="报告分页"><button type="button" className="button button-secondary" onClick={() => setPage(current - 1)} disabled={current <= 1}>上一页</button><span>第 {current} / {page.pages} 页</span><button type="button" className="button button-secondary" onClick={() => setPage(current + 1)} disabled={current >= page.pages}>下一页</button></nav> : null}
    </section>
  );
}
