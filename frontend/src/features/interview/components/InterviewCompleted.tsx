import { Link } from "react-router-dom";

export function InterviewCompleted({ sessionId }: { sessionId: string }) { return <section className="interview-card terminal-card"><p className="eyebrow">MISSION COMPLETE</p><h2>面试完成</h2><p>你的回答已经保存，现在可以生成包含雷达图、问答回放和改进建议的报告。</p><Link className="button button-primary" to={`/interview/${sessionId}/report`}>生成面试报告</Link></section>; }
