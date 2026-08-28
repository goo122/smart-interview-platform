import { Link } from "react-router-dom";
import type { InterviewSession } from "@/features/interview/types";

export function InterviewFailure({ session }: { session: InterviewSession }) { return <section className="interview-card terminal-card"><p className="eyebrow">准备未完成</p><h2>这场面试暂时无法继续</h2><p>{session.failureMessage || "服务暂时不可用，请重新创建面试。"}</p><Link className="button button-primary" to="/interview">重新设置</Link></section>; }

