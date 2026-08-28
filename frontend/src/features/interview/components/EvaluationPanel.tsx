import type { InterviewEvaluation } from "@/features/interview/types";

const dimensions = [
  ["技术能力", "technicalScore"], ["相关性", "relevanceScore"], ["表达清晰", "clarityScore"], ["回答深度", "depthScore"],
] as const;

export function EvaluationPanel({ evaluation }: { evaluation: InterviewEvaluation }) {
  return <section className="evaluation-panel"><div className="evaluation-header"><div><p className="eyebrow">本轮评分</p><h3>{evaluation.overallScore} <small>/ 100</small></h3></div><span className="score-badge">已完成</span></div><div className="score-grid">{dimensions.map(([label, key]) => { const score = evaluation[key]; return <div key={key}><span>{label}</span><strong>{score}</strong><i><b style={{ width: `${Math.max(0, Math.min(100, score))}%` }} /></i></div>; })}</div><p className="evaluation-feedback">{evaluation.feedback}</p><div className="evaluation-columns"><List title="优势" items={evaluation.strengths} /><List title="可提升" items={evaluation.weaknesses} /><List title="建议" items={evaluation.suggestedImprovements} /></div></section>;
}

function List({ title, items }: { title: string; items: string[] }) { return <div><h4>{title}</h4>{items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="panel-muted">暂无</p>}</div>; }

