import { Link, useParams } from "react-router-dom";
import { toUserMessage } from "@/api/errors";
import { InterviewCompleted } from "@/features/interview/components/InterviewCompleted";
import { InterviewFailure } from "@/features/interview/components/InterviewFailure";
import { InterviewPreparation } from "@/features/interview/components/InterviewPreparation";
import { InterviewRoom } from "@/features/interview/components/InterviewRoom";
import { useCurrentTurn, useInterviewSession } from "@/features/interview/hooks";
import type { InterviewStatus, InterviewTurn } from "@/features/interview/types";

export function InterviewSessionPage() {
  const { sessionId = "" } = useParams();
  const sessionQuery = useInterviewSession(sessionId);
  const session = sessionQuery.data ? { ...sessionQuery.data, status: sessionQuery.data.status as InterviewStatus } : undefined;
  const currentTurnQuery = useCurrentTurn(sessionId, session?.status === "IN_PROGRESS");
  if (sessionQuery.isPending) return <section className="loading-screen"><span className="spinner" />正在恢复面试会话…</section>;
  if (sessionQuery.isError || !session) return <section className="interview-card terminal-card"><h2>找不到这场面试</h2><p>{toUserMessage(sessionQuery.error)}</p><Link className="button button-primary" to="/interview">返回设置</Link></section>;
  if (session.status === "FAILED") return <InterviewFailure session={session} />;
  if (session.status === "CANCELLED") return <section className="interview-card terminal-card"><h2>面试已取消</h2><p>这场面试已经结束，不能继续开始或答题。</p><Link className="button button-primary" to="/interview">重新创建</Link></section>;
  if (session.status === "COMPLETED") return <InterviewCompleted sessionId={session.sessionId} />;
  if (session.status === "CREATED" || session.status === "PREPARING" || session.status === "READY") return <InterviewPreparation session={session} />;
  if (currentTurnQuery.isError && !currentTurnQuery.data) return <section className="interview-card terminal-card"><h2>正在准备当前问题</h2><p>{toUserMessage(currentTurnQuery.error)}</p><button className="button button-secondary" type="button" onClick={() => void currentTurnQuery.refetch()}>重试</button></section>;
  if (!currentTurnQuery.data) return <section className="loading-screen"><span className="spinner" />正在获取当前问题…</section>;
  return <InterviewRoom session={session} turn={{ ...currentTurnQuery.data, status: currentTurnQuery.data.status as InterviewTurn["status"], turnType: currentTurnQuery.data.turnType as InterviewTurn["turnType"] }} />;
}
