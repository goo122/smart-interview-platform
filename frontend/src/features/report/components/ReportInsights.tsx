type Props = {
  strengths: string[];
  weaknesses: string[];
  suggestedImprovements: string[];
  actionPlan: string[];
};

export function ReportInsights({ strengths, weaknesses, suggestedImprovements, actionPlan }: Props) {
  return (
    <section className="report-insights" aria-label="面试建议">
      <InsightList title="优势" items={strengths} tone="positive" empty="暂未记录优势" />
      <InsightList title="待提升" items={weaknesses} tone="caution" empty="暂未记录待提升项" />
      <InsightList title="改进建议" items={suggestedImprovements} tone="neutral" empty="暂未记录改进建议" />
      <div className="report-insight-block report-action-plan">
        <div className="report-section-heading"><h2>行动计划</h2><span>{actionPlan.length} 项</span></div>
        {actionPlan.length ? (
          <ol>{actionPlan.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ol>
        ) : <p className="report-empty-copy">暂无行动计划</p>}
      </div>
    </section>
  );
}

function InsightList({ title, items, tone, empty }: { title: string; items: string[]; tone: string; empty: string }) {
  return (
    <div className={`report-insight-block ${tone}`}>
      <div className="report-section-heading"><h2>{title}</h2><span>{items.length} 项</span></div>
      {items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="report-empty-copy">{empty}</p>}
    </div>
  );
}
