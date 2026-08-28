import { Link } from "react-router-dom";
import { reportStatusLabels, type ReportStatus } from "@/features/report/types";

type Props = {
  status: ReportStatus;
  message?: string | null;
  onRetry?: () => void;
  retrying?: boolean;
};

export function ReportStatusView({ status, message, onRetry, retrying }: Props) {
  const failed = status === "FAILED";
  return (
    <section className={`report-status-card ${failed ? "failed" : "pending"}`}>
      <p className="eyebrow">REPORT STATUS</p>
      <div className="report-status-icon" aria-hidden="true">{failed ? "!" : "…"}</div>
      <h1>{failed ? "报告生成失败" : reportStatusLabels[status]}</h1>
      <p>{message || (failed ? "报告暂时无法生成，请稍后重试。" : "系统正在整理面试评分和问答快照，请稍候。")}</p>
      {failed && onRetry ? <button className="button button-primary" type="button" onClick={onRetry} disabled={retrying}>{retrying ? "重试中…" : "重新生成报告"}</button> : null}
      <Link className="button button-quiet" to="/interview/reports">返回报告列表</Link>
    </section>
  );
}
