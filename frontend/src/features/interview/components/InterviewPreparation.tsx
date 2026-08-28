import { Link } from "react-router-dom";
import { toUserMessage } from "@/api/errors";
import { useInterviewMutations } from "@/features/interview/hooks";
import { difficultyLabels, interviewTypeLabels, type InterviewSession } from "@/features/interview/types";

export function InterviewPreparation({ session }: { session: InterviewSession }) {
  const { start } = useInterviewMutations(session.sessionId);
  const progress = Math.max(0, Math.min(100, session.preparationProgress));
  return (
    <section className="interview-card preparation-card">
      <p className="eyebrow">准备状态</p>
      <h2>{session.status === "READY" ? "题目已准备好" : "正在分析你的面试材料"}</h2>
      <p className="panel-muted">{session.status === "READY" ? "确认下面的面试参数后即可开始。" : "系统正在根据岗位和简历生成专属题目，请稍候。"}</p>
      <div className="preparation-progress"><span style={{ width: `${progress}%` }} /></div><small>{progress}%</small>
      <div className="interview-meta-grid"><span>岗位<strong>{session.jobTitle}</strong></span><span>类型<strong>{interviewTypeLabels[session.interviewType as keyof typeof interviewTypeLabels] ?? session.interviewType}</strong></span><span>难度<strong>{difficultyLabels[session.difficulty as keyof typeof difficultyLabels] ?? session.difficulty}</strong></span><span>基础题<strong>{session.questionCount} 道</strong></span></div>
      {start.isError ? <p className="form-error" role="alert">{toUserMessage(start.error)}</p> : null}
      {session.status === "READY" ? <button className="button button-primary" type="button" onClick={() => start.mutate(session.sessionId)} disabled={start.isPending}>{start.isPending ? "启动中…" : "开始面试"}</button> : null}
      {session.status === "FAILED" ? <Link className="button button-secondary" to="/interview">返回设置</Link> : null}
    </section>
  );
}

