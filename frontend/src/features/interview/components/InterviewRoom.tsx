import { toUserMessage } from "@/api/errors";
import { useInterviewMutations, useInterviewTurns } from "@/features/interview/hooks";
import { toAnswerPayload } from "@/features/interview/schemas";
import { difficultyLabels, interviewTypeLabels, type InterviewSession, type InterviewTurn } from "@/features/interview/types";
import { AnswerEditor } from "@/features/interview/components/AnswerEditor";
import { EvaluationPanel } from "@/features/interview/components/EvaluationPanel";
import { InterviewProgress } from "@/features/interview/components/InterviewProgress";
import { QuestionCard } from "@/features/interview/components/QuestionCard";

export function InterviewRoom({ session, turn }: { session: InterviewSession; turn: InterviewTurn }) {
  const { submit, cancel } = useInterviewMutations(session.sessionId);
  const turnsQuery = useInterviewTurns(session.sessionId);
  const prior = (turnsQuery.data ?? []).filter((item) => item.turnId !== turn.turnId && item.evaluation).sort((a, b) => a.sequence - b.sequence).at(-1);
  const submitAnswer = async (answer: string, requestId: string) => { await submit.mutateAsync({ id: session.sessionId, payload: toAnswerPayload(turn.turnId, answer, requestId) }); };
  return <section className="interview-room"><header className="room-header"><div><p className="eyebrow">面试房间</p><h1>{session.jobTitle}</h1><div className="room-subtitle"><span>{interviewTypeLabels[session.interviewType as keyof typeof interviewTypeLabels] ?? session.interviewType}</span><span>{difficultyLabels[session.difficulty as keyof typeof difficultyLabels] ?? session.difficulty}</span></div></div><button type="button" className="button button-quiet" onClick={() => { if (window.confirm("确定退出并取消这场面试吗？")) cancel.mutate(session.sessionId); }} disabled={cancel.isPending}>退出面试</button></header><InterviewProgress session={session} turn={turn} /><QuestionCard turn={turn} />{turn.status === "EVALUATING" ? <div className="evaluating-state" role="status"><span className="spinner" />正在评分，请稍候…</div> : null}{turn.evaluation ? <EvaluationPanel evaluation={turn.evaluation} /> : prior?.evaluation ? <details className="previous-evaluation" open><summary>上一轮评分摘要</summary><EvaluationPanel evaluation={prior.evaluation} /></details> : null}{turn.canAnswer && turn.status === "WAITING_ANSWER" ? <AnswerEditor key={turn.turnId} turnId={turn.turnId} onSubmit={submitAnswer} /> : null}{submit.isError ? <p className="form-error" role="alert">{toUserMessage(submit.error)}</p> : null}{turn.status === "FAILED" ? <p className="panel-error" role="alert">本轮评分失败，请稍后重试或结束面试。</p> : null}</section>;
}

