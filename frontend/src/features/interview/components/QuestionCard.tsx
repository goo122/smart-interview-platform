import type { InterviewTurn } from "@/features/interview/types";

export function QuestionCard({ turn }: { turn: InterviewTurn }) {
  const followUp = turn.turnType === "FOLLOW_UP";
  return <div className={`question-card ${followUp ? "follow-up" : "primary"}`}><div className="question-kicker"><span>{followUp ? "FOLLOW-UP · 追问" : "PRIMARY · 基础题"}</span>{followUp ? <span>第 {turn.followUpDepth} 次追问</span> : null}</div><p>{turn.question}</p></div>;
}

