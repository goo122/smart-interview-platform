import { Link } from "react-router-dom";

export function InterviewCompleted() { return <section className="interview-card terminal-card"><p className="eyebrow">MISSION COMPLETE</p><h2>面试完成</h2><p>你的回答已经保存。报告页面将在下一阶段提供完整的雷达图、回放和改进建议。</p><Link className="button button-primary" to="/interview/reports">查看报告入口</Link></section>; }

