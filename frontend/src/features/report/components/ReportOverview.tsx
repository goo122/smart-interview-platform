import {
  asGeneratedBy,
  dimensionLabels,
  generatedByLabels,
  reportDimensions,
  reportScore,
  safeScore,
  type Report,
} from "@/features/report/types";

type Props = { report: Report };

export function ReportOverview({ report }: Props) {
  const generatedBy = asGeneratedBy(report.generatedBy);
  const overallScore = safeScore(report.overallScore);

  return (
    <>
      <section className="report-hero-card">
        <div>
          <p className="eyebrow">INTERVIEW REPORT</p>
          <h1>{report.jobTitle}</h1>
          <div className="report-meta-line">
            <span>{report.interviewType}</span>
            <span>{report.difficulty}</span>
            <span>{generatedByLabels[generatedBy]}</span>
          </div>
        </div>
        <div className="report-total-score">
          <span>总分</span>
          <strong>{overallScore === null ? "数据异常" : overallScore}</strong>
          <small>/ 100</small>
        </div>
      </section>
      <section className="report-summary-card">
        <div className="report-section-heading">
          <div>
            <p className="eyebrow">SUMMARY</p>
            <h2>综合表现</h2>
          </div>
          {report.recommendedLevel ? <span className="report-level">建议水平：{report.recommendedLevel}</span> : null}
        </div>
        <p className="report-summary-text">{report.summary || "暂无综合总结。"}</p>
        <div className="report-dimension-grid">
          {reportDimensions.map((dimension) => {
            const score = reportScore(report, dimension);
            return (
              <div className="report-dimension-card" key={dimension}>
                <span>{dimensionLabels[dimension]}</span>
                <strong>{score === null ? "数据异常" : score}</strong>
                <i><b style={{ width: score === null ? "0%" : `${score}%` }} /></i>
              </div>
            );
          })}
        </div>
        <dl className="report-facts">
          <div><dt>生成方式</dt><dd>{generatedByLabels[generatedBy]}</dd></div>
          <div><dt>聚合版本</dt><dd>{report.aggregationVersion}</dd></div>
          <div><dt>生成时间</dt><dd>{new Date(report.completedAt ?? report.updatedAt).toLocaleString("zh-CN")}</dd></div>
        </dl>
      </section>
    </>
  );
}
