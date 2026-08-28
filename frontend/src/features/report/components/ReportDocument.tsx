import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import { reportDimensions, reportScore, type Report } from "@/features/report/types";
import { ReportInsights } from "@/features/report/components/ReportInsights";
import { ReportOverview } from "@/features/report/components/ReportOverview";
import { ReportReplay } from "@/features/report/components/ReportReplay";

const RadarChart = lazy(() => import("@/features/report/components/RadarChart"));

export function ReportDocument({ report }: { report: Report }) {
  const radarScores = reportDimensions.map((dimension) => ({
    dimension,
    score: reportScore(report, dimension),
  }));
  return (
    <div className="report-document">
      <div className="report-toolbar">
        <Link className="button button-quiet" to="/interview/reports">← 报告列表</Link>
        <button className="button button-secondary print-button" type="button" onClick={() => window.print()}>打印报告</button>
      </div>
      <ReportOverview report={report} />
      <Suspense fallback={<section className="report-radar radar-loading">正在加载能力雷达…</section>}>
        <RadarChart scores={radarScores} />
      </Suspense>
      <ReportInsights
        strengths={report.strengths}
        weaknesses={report.weaknesses}
        suggestedImprovements={report.suggestedImprovements}
        actionPlan={report.actionPlan}
      />
      <ReportReplay items={report.items} />
    </div>
  );
}
