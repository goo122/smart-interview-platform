import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toUserMessage } from "@/api/errors";
import { useKnowledgeBaseReadiness } from "@/features/knowledge/hooks";
import { createRequestId } from "@/features/interview/state";
import { useInterviewMutations } from "@/features/interview/hooks";
import { interviewSetupSchema, toCreatePayload, type InterviewSetupForm } from "@/features/interview/schemas";
import { difficultyLabels, interviewTypeLabels } from "@/features/interview/types";

export function InterviewSetupForm() {
  const navigate = useNavigate();
  const readiness = useKnowledgeBaseReadiness();
  const { create } = useInterviewMutations();
  const [requestId] = useState(createRequestId);
  const { register, control, handleSubmit, formState: { errors } } = useForm<InterviewSetupForm>({
    resolver: zodResolver(interviewSetupSchema),
    defaultValues: { knowledgeBaseId: "", jobTitle: "", jobDescription: "", interviewType: "TECHNICAL", difficulty: "MEDIUM", questionCount: 8, requestId },
  });
  const bases = readiness.data?.records ?? [];
  const readyBases = bases.filter((_base, index) =>
    (readiness.documentQueries[index]?.data?.records ?? []).some((document) => document.status === "READY"),
  );

  const submit = async (form: InterviewSetupForm) => {
    try {
      const session = await create.mutateAsync(toCreatePayload({ ...form, requestId }));
      navigate(`/interview/${session.sessionId}`);
    } catch {
      // The mutation error is rendered below using the safe API message.
    }
  };

  return (
    <section className="interview-page interview-setup-page">
      <div className="interview-heading">
        <div><p className="eyebrow">INTERVIEW STUDIO</p><h1>开始一场模拟面试</h1><p>选择一份已就绪的简历知识库，告诉我们你想练习的岗位。</p></div>
        <span className="interview-step">01 / 设置</span>
      </div>
      {readiness.isPending ? <p className="panel-muted">正在检查可用简历…</p> : null}
      {readiness.isError ? <p className="panel-error" role="alert">{toUserMessage(readiness.error)}</p> : null}
      {!readiness.isPending && !readyBases.length ? (
        <div className="interview-empty-card">
          <h2>还没有可用于面试的简历</h2>
          <p>请先在聊天页的知识库区域上传 PDF，并等待文档状态变为“已就绪”。</p>
          <Link className="button button-primary" to="/chat">前往上传简历</Link>
        </div>
      ) : (
        <form className="interview-form" onSubmit={handleSubmit(submit)} noValidate>
          <label className="form-field" htmlFor="interview-knowledge-base"><span>简历知识库</span><Controller name="knowledgeBaseId" control={control} render={({ field }) => <select id="interview-knowledge-base" {...field}><option value="" disabled>选择已就绪的知识库</option>{readyBases.map((base) => <option key={base.id} value={base.id}>{base.name}</option>)}</select>} />{errors.knowledgeBaseId ? <small className="field-error">{errors.knowledgeBaseId.message}</small> : null}</label>
          <div className="interview-form-grid">
            <label className="form-field" htmlFor="interview-job-title"><span>岗位名称</span><input id="interview-job-title" {...register("jobTitle")} placeholder="例如：后端工程师" maxLength={200} />{errors.jobTitle ? <small className="field-error">{errors.jobTitle.message}</small> : null}</label>
            <label className="form-field" htmlFor="interview-type"><span>面试类型</span><select id="interview-type" {...register("interviewType")} >{Object.entries(interviewTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label className="form-field" htmlFor="interview-difficulty"><span>难度</span><select id="interview-difficulty" {...register("difficulty")} >{Object.entries(difficultyLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label className="form-field" htmlFor="interview-question-count"><span>基础题数量</span><input id="interview-question-count" {...register("questionCount", { valueAsNumber: true })} type="number" min={3} max={20} /></label>
          </div>
          <label className="form-field" htmlFor="interview-job-description"><span>岗位描述</span><textarea id="interview-job-description" {...register("jobDescription")} placeholder="粘贴岗位职责、技术栈和能力要求" maxLength={20000} rows={7} />{errors.jobDescription ? <small className="field-error">{errors.jobDescription.message}</small> : null}</label>
          {create.isError ? <p className="form-error" role="alert">{toUserMessage(create.error)}</p> : null}
          <button className="button button-primary" type="submit" disabled={create.isPending || !readyBases.length}>{create.isPending ? "创建准备中…" : "创建面试"}</button>
        </form>
      )}
    </section>
  );
}
