import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { ReviewFeedback } from "@/components/interview/report/types";

type InterviewConclusionCardProps = {
  interviewDirection: string | null;
  reviewFeedback: ReviewFeedback;
  isRecordLoading: boolean;
  recordError: string | null;
};

type SectionProps = {
  title: string;
  items: string[];
  emptyText: string;
  tone?: "default" | "positive" | "warning";
};

function FeedbackSection({
  title,
  items,
  emptyText,
  tone = "default",
}: SectionProps) {
  const toneClass =
    tone === "positive"
      ? "bg-emerald-50 text-emerald-700"
      : tone === "warning"
        ? "bg-amber-50 text-amber-700"
        : "bg-slate-50 text-slate-600";

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
        {title}
      </p>
      {items.length > 0 ? (
        <div className="space-y-2">
          {items.map((item, index) => (
            <motion.div
              key={`${title}-${index}-${item}`}
              className={`rounded-xl px-3 py-2 text-sm leading-6 ${toneClass}`}
              initial={{ opacity: 0, y: 10, filter: "blur(3px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{
                duration: 0.24,
                delay: index * 0.06,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              {item}
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-400">
          {emptyText}
        </div>
      )}
    </div>
  );
}

export default function InterviewConclusionCard({
  interviewDirection,
  reviewFeedback,
  isRecordLoading,
  recordError,
}: InterviewConclusionCardProps) {
  return (
    <Card className="border-slate-100 p-6">
      <div className="space-y-2">
        <p className="text-sm font-semibold text-slate-900">面试结论</p>
        <p className="text-xs text-slate-500">
          {interviewDirection
            ? `面试方向：${interviewDirection}`
            : "面试方向暂无数据"}
        </p>
      </div>

      <Separator className="my-4" />

      {isRecordLoading && (
        <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500">
          正在生成本场面试回访反馈...
        </div>
      )}

      {recordError && (
        <div className="rounded-xl bg-rose-50 px-3 py-3 text-sm text-rose-600">
          {recordError}
        </div>
      )}

      {!isRecordLoading && !recordError && (
        <div className="space-y-5">
          <motion.div
            className="rounded-2xl bg-slate-900 px-4 py-4 text-slate-50"
            initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          >
            <p className="text-xs font-medium tracking-[0.18em] text-slate-300">
              总体评价
            </p>
            <p className="mt-2 text-sm leading-6">
              {reviewFeedback.overallComment ??
                "本次面试已完成，报告数据已同步。"}
            </p>
          </motion.div>

          <FeedbackSection
            title="亮点总结"
            items={reviewFeedback.highlights}
            emptyText="当前暂无可展示的亮点总结"
            tone="positive"
          />

          <FeedbackSection
            title="待改进点"
            items={reviewFeedback.improvementTips}
            emptyText="当前暂无待改进点"
            tone="warning"
          />
        </div>
      )}
    </Card>
  );
}
