import type { InterviewSession, InterviewTurn } from "@/features/interview/types";

export function InterviewProgress({ session, turn }: { session: InterviewSession; turn?: InterviewTurn }) {
  const current = Math.min(session.questionCount, Math.max(0, session.currentQuestionIndex + (turn?.turnType === "PRIMARY" ? 1 : 0)));
  return <div className="interview-progress"><span>基础题进度</span><strong>{current} / {session.questionCount}</strong><div><i style={{ width: `${session.questionCount ? (current / session.questionCount) * 100 : 0}%` }} /></div></div>;
}

