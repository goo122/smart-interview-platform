import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import type { ChangeEvent, RefObject } from "react";
import ErrorNotice from "@/components/feedback/ErrorNotice";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { INTERVIEW_DEFAULTS } from "@/lib/constants";

const RESUME_UPLOAD_STAGES = [
  "正在上传简历",
  "正在解析简历",
  "正在生成面试题",
] as const;

type InterviewResumeUploadCardProps = {
  fileInputRef: RefObject<HTMLInputElement | null>;
  isResumeUploading: boolean;
  showUploadButton: boolean;
  resumeUploadStage: number;
  resumeLocalFile: File | null;
  resumeFileUrl: string | null;
  resumeName: string | null;
  resumePreviewError: string | null;
  resumeUploadError: string | null;
  interviewError: string | null;
  onResumeFileSelect: (event: ChangeEvent<HTMLInputElement>) => void;
  onOpenResume: () => void;
};

export default function InterviewResumeUploadCard({
  fileInputRef,
  isResumeUploading,
  showUploadButton,
  resumeUploadStage,
  resumeLocalFile,
  resumeFileUrl,
  resumeName,
  resumePreviewError,
  resumeUploadError,
  interviewError,
  onResumeFileSelect,
  onOpenResume,
}: InterviewResumeUploadCardProps) {
  const normalizedUploadStage = Math.min(
    Math.max(resumeUploadStage, 0),
    RESUME_UPLOAD_STAGES.length - 1,
  );
  const activeUploadLabel = RESUME_UPLOAD_STAGES[normalizedUploadStage];
  const progressPercent =
    ((normalizedUploadStage + 1) / RESUME_UPLOAD_STAGES.length) * 100;
  const hasResumeEntry = Boolean(
    resumeLocalFile || resumeFileUrl || resumeName || resumePreviewError,
  );

  return (
    <Card className="border-dashed border-slate-200 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-900">
            上传简历后开始面试
          </p>
          <p className="mt-1 text-xs text-slate-500">
            当前支持 PDF，系统会基于简历内容生成面试题。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept={INTERVIEW_DEFAULTS.resumeAccept}
            className="hidden"
            onChange={onResumeFileSelect}
          />
          {showUploadButton ? (
            <Button
              variant="outline"
              className="rounded-full"
              disabled={isResumeUploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {isResumeUploading ? "上传中..." : "上传简历"}
            </Button>
          ) : null}
          {hasResumeEntry ? (
            <Button
              variant="ghost"
              className="rounded-full text-slate-600"
              onClick={onOpenResume}
            >
              查看简历
            </Button>
          ) : null}
          {resumeName ? (
            <span className="max-w-[200px] truncate text-xs text-slate-500">
              {resumeName}
            </span>
          ) : null}
        </div>
      </div>

      {resumeUploadError ? (
        <div className="mt-3">
          <ErrorNotice title="简历上传失败" description={resumeUploadError} />
        </div>
      ) : null}

      {isResumeUploading ? (
        <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-4 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <div className="relative mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600">
                <motion.div
                  aria-hidden
                  className="absolute inset-0 rounded-xl border border-slate-300/70"
                  animate={{
                    opacity: [0.25, 0.7, 0.25],
                    scale: [0.95, 1.02, 0.95],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                />
                <Loader2 className="relative h-4 w-4 animate-spin" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-900">
                  {activeUploadLabel}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {resumeName || "当前简历"}
                  正在处理中，请稍候，完成后会自动进入面试。
                </p>
              </div>
            </div>
            <div className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-500">
              {normalizedUploadStage + 1}/{RESUME_UPLOAD_STAGES.length}
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            {RESUME_UPLOAD_STAGES.map((stage, index) => {
              const isCompleted = index < normalizedUploadStage;
              const isCurrent = index === normalizedUploadStage;
              const stageStateText = isCompleted
                ? "已完成"
                : isCurrent
                  ? "进行中"
                  : "等待中";

              return (
                <div
                  key={stage}
                  className={[
                    "flex items-center gap-2 rounded-xl border px-3 py-2.5 text-xs transition-colors",
                    isCompleted
                      ? "border-emerald-200 bg-emerald-50/80 text-emerald-700"
                      : "",
                    isCurrent
                      ? "border-slate-300 bg-white text-slate-700 shadow-sm"
                      : "",
                    !isCompleted && !isCurrent
                      ? "border-slate-200 bg-white/70 text-slate-400"
                      : "",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold",
                      isCompleted
                        ? "border-emerald-500 bg-emerald-500 text-white"
                        : "",
                      isCurrent
                        ? "border-slate-400 bg-slate-100 text-slate-700"
                        : "",
                      !isCompleted && !isCurrent
                        ? "border-slate-300 bg-white text-slate-400"
                        : "",
                    ].join(" ")}
                  >
                    {isCompleted ? <Check className="h-3 w-3" /> : index + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium">{stage}</p>
                    <p className="mt-0.5 text-[11px] opacity-80">
                      {stageStateText}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between text-[11px] text-slate-500">
              <span>处理进度</span>
              <span>{Math.round(progressPercent)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
              <motion.div
                className="h-full rounded-full bg-slate-700"
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.45, ease: "easeOut" }}
              />
            </div>
          </div>
        </div>
      ) : null}

      {interviewError ? (
        <div className="mt-3">
          <ErrorNotice title="面试流程异常" description={interviewError} />
        </div>
      ) : null}
    </Card>
  );
}
