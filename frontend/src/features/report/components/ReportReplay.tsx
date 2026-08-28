import { dimensionLabels, formatReportDate, itemScore, type ReportItem } from "@/features/report/types";
import { ReportSources } from "@/features/report/components/ReportSources";

export function ReportReplay({ items }: { items: readonly ReportItem[] }) {
  const ordered = [...items].sort((left, right) => left.sequence - right.sequence);
  const sequenceByTurnId = new Map(ordered.map((item) => [item.turnId, item.sequence]));
  return (
    <section className="report-replay" aria-labelledby="report-replay-title">
      <div className="report-section-heading">
        <div><p className="eyebrow">PLAYBACK</p><h2 id="report-replay-title">问答回放</h2></div>
        <span>{ordered.length} 轮</span>
      </div>
      {ordered.length ? ordered.map((item) => <ReplayItem item={item} parentSequence={item.parentTurnId ? sequenceByTurnId.get(item.parentTurnId) : undefined} key={item.id} />) : <p className="report-empty-copy">暂无可回放内容，报告数据可能不完整。</p>}
    </section>
  );
}

function ReplayItem({ item, parentSequence }: { item: ReportItem; parentSequence?: number }) {
  const followUp = item.turnType === "FOLLOW_UP";
  const overall = itemScore(item, "overall");
  return (
    <article className={`report-replay-item ${followUp ? "follow-up" : "primary"}`}>
      <header>
        <div><span className="replay-sequence">第 {item.sequence} 轮</span><span className="replay-type">{followUp ? "FOLLOW_UP · 动态追问" : "PRIMARY · 基础题"}</span></div>
        <time dateTime={item.createdAt}>{formatReportDate(item.createdAt)}</time>
      </header>
      {followUp && item.parentTurnId ? <p className="replay-parent">追问承接第 {parentSequence ?? "关联"} 轮回答</p> : null}
      <div className="replay-question"><span>问题</span><p>{item.question}</p></div>
      <div className="replay-answer"><span>回答</span><p>{item.answer || "数据异常：未保存回答"}</p></div>
      <details className="replay-evaluation">
        <summary>{overall === null ? "评分数据异常" : `评分 ${overall} / 100`} · 查看详细反馈</summary>
        <div className="replay-score-row">
          {(["technical", "relevance", "clarity", "depth"] as const).map((dimension) => {
            const score = itemScore(item, dimension);
            return <span key={dimension}>{dimensionLabels[dimension]}：{score === null ? "异常" : score}</span>;
          })}
        </div>
        <p className="replay-feedback">{item.feedback || "暂无反馈"}</p>
        <div className="replay-columns">
          <ReplayList title="优势" items={item.strengths} />
          <ReplayList title="弱点" items={item.weaknesses} />
          <ReplayList title="改进建议" items={item.suggestedImprovements} />
        </div>
      </details>
      <div className="replay-sources"><span>来源快照</span><ReportSources sources={item.sources} /></div>
    </article>
  );
}

function ReplayList({ title, items }: { title: string; items: readonly string[] }) {
  return <div><h3>{title}</h3>{items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="report-empty-copy">暂无</p>}</div>;
}
