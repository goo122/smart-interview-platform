import { z } from "zod";
import type { CreateInterviewSessionRequest, SubmitInterviewAnswerRequest } from "@/api/generated";
import { frontendEnv } from "@/config/env";

export const interviewSetupSchema = z.object({
  knowledgeBaseId: z.string().min(1, "请选择一个可用知识库"),
  jobTitle: z.string().trim().min(1, "请输入岗位名称").max(200, "岗位名称不能超过 200 个字符"),
  jobDescription: z.string().trim().min(1, "请输入岗位描述").max(20000, "岗位描述不能超过 20000 个字符"),
  interviewType: z.enum(["TECHNICAL", "BEHAVIORAL", "MIXED"]),
  difficulty: z.enum(["EASY", "MEDIUM", "HARD"]),
  questionCount: z.number().int().min(3, "题目数量至少为 3").max(20, "题目数量最多为 20"),
  requestId: z.string().min(1).max(128),
});

export type InterviewSetupForm = z.infer<typeof interviewSetupSchema>;

export const answerSchema = z.object({
  answer: z.string().trim().min(frontendEnv.interviewMinAnswerLength, `回答至少需要 ${frontendEnv.interviewMinAnswerLength} 个字符`).max(frontendEnv.interviewMaxAnswerLength, `回答不能超过 ${frontendEnv.interviewMaxAnswerLength} 个字符`),
});

export type AnswerForm = z.infer<typeof answerSchema>;

export const toCreatePayload = (form: InterviewSetupForm): CreateInterviewSessionRequest => ({
  knowledgeBaseId: form.knowledgeBaseId,
  jobTitle: form.jobTitle.trim(),
  jobDescription: form.jobDescription.trim(),
  interviewType: form.interviewType,
  difficulty: form.difficulty,
  questionCount: form.questionCount,
  requestId: form.requestId,
});

export const toAnswerPayload = (
  turnId: string,
  answer: string,
  requestId: string,
): SubmitInterviewAnswerRequest => ({ turnId, answer: answer.trim(), requestId });
