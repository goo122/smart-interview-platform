import { useRef, useState } from "react";
import { frontendEnv } from "@/config/env";
import { answerSchema } from "@/features/interview/schemas";
import { createRequestId } from "@/features/interview/state";

type Props = { turnId: string; disabled?: boolean; onSubmit: (answer: string, requestId: string) => Promise<void> };

export function AnswerEditor({ turnId, disabled, onSubmit }: Props) {
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(createRequestId());
  const [submitting, setSubmitting] = useState(false);
  const submit = async () => {
    const result = answerSchema.safeParse({ answer });
    if (!result.success) { setError(result.error.issues[0]?.message ?? "请完善回答"); return; }
    setError(null); setSubmitting(true);
    try { await onSubmit(result.data.answer, requestId.current); } catch { /* page renders mutation error */ } finally { setSubmitting(false); }
  };
  return <div className="answer-editor"><textarea value={answer} onChange={(event) => { setAnswer(event.target.value); if (error) setError(null); }} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); void submit(); } }} disabled={disabled || submitting} placeholder="写下你的回答…（Ctrl/Cmd + Enter 提交）" maxLength={frontendEnv.interviewMaxAnswerLength} rows={8} aria-label={`回答 ${turnId}`} /><div className="answer-editor-footer"><span>{answer.length} / {frontendEnv.interviewMaxAnswerLength}</span><button className="button button-primary" type="button" onClick={() => void submit()} disabled={disabled || submitting}>{submitting ? "提交中…" : "提交回答"}</button></div>{error ? <p className="field-error" role="alert">{error}</p> : null}</div>;
}
