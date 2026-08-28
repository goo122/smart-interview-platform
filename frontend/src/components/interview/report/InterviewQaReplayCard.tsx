import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ROUTES } from "@/lib/constants";
import {
  buildReportSearch,
  getReportSessionIdFromLocation,
} from "@/lib/interviewReportRoute";
import { cn } from "@/lib/utils";
import type { QaReview } from "@/components/interview/report/types";

type InterviewQaReplayCardProps = {
  qaReviews: QaReview[];
  isRecordLoading: boolean;
  recordError: string | null;
  variant?: "default" | "detail";
};

type QaReplayGroup = {
  id: string;
  parent: QaReview;
  followUps: QaReview[];
};

const FOLLOW_UP_NUMBER_PATTERN = /^(.*?)-F\d+$/iu;

const extractParentQuestionNumber = (questionNumber?: string | null) => {
  if (!questionNumber) return null;
  const normalized = questionNumber.trim();
  if (!normalized) return null;
  const matched = normalized.match(FOLLOW_UP_NUMBER_PATTERN);
  if (matched?.[1]) {
    return matched[1].trim() || null;
  }
  return normalized;
};

export default function InterviewQaReplayCard({
  qaReviews,
  isRecordLoading,
  recordError,
  variant = "default",
}: InterviewQaReplayCardProps) {
  const isDetail = variant === "detail";
  const location = useLocation();
  const reportSessionId = getReportSessionIdFromLocation(location);
  const detailLink = `${ROUTES.interviewReportDetail}${buildReportSearch(reportSessionId)}`;
  const [expandedFeedbackMap, setExpandedFeedbackMap] = useState<
    Record<string, boolean>
  >({});

  const resolveRoundLabel = (item: QaReview, index: number) => {
    if (item.isFollowUp) {
      const followUpRound =
        typeof item.followUpCount === "number" && item.followUpCount > 0
          ? item.followUpCount
          : null;
      if (item.questionNumber) {
        return `追问 ${item.questionNumber}${followUpRound ? `（第 ${followUpRound} 轮）` : ""}`;
      }
      return followUpRound
        ? `追问（第 ${followUpRound} 轮）`
        : `追问（第 ${index + 1} 条）`;
    }
    if (item.questionNumber) {
      return `主问题 ${item.questionNumber}`;
    }
    return `第 ${index + 1} 题`;
  };

  const qaReplayGroups = useMemo(() => {
    const groups: QaReplayGroup[] = [];
    const mainGroupByQuestionNumber = new Map<string, QaReplayGroup>();
    let latestMainGroup: QaReplayGroup | null = null;

    qaReviews.forEach((item, index) => {
      const followUpParentQuestionNumber = item.isFollowUp
        ? extractParentQuestionNumber(item.questionNumber)
        : null;
      const matchedMainGroup =
        (followUpParentQuestionNumber
          ? mainGroupByQuestionNumber.get(followUpParentQuestionNumber)
          : null) ?? (!followUpParentQuestionNumber ? latestMainGroup : null);

      if (item.isFollowUp && matchedMainGroup) {
        matchedMainGroup.followUps.push(item);
        return;
      }

      const group: QaReplayGroup = {
        id: `${item.questionNumber || "qa"}-${index}`,
        parent: item,
        followUps: [],
      };
      groups.push(group);

      if (!item.isFollowUp) {
        latestMainGroup = group;
        const mainQuestionNumber = extractParentQuestionNumber(
          item.questionNumber,
        );
        if (mainQuestionNumber) {
          mainGroupByQuestionNumber.set(mainQuestionNumber, group);
        }
      }
    });

    return groups;
  }, [qaReviews]);

  const toggleFeedback = (feedbackKey: string) => {
    setExpandedFeedbackMap((prev) => ({
      ...prev,
      [feedbackKey]: !prev[feedbackKey],
    }));
  };

  const renderReviewItem = ({
    item,
    label,
    feedbackKey,
    isChild,
    animationDelay = 0,
  }: {
    item: QaReview;
    label: string;
    feedbackKey: string;
    isChild: boolean;
    animationDelay?: number;
  }) => {
    const feedback = item.feedback?.trim() || "";
    const isFeedbackVisible = Boolean(expandedFeedbackMap[feedbackKey]);
    const showFollowUpBadge = isChild || Boolean(item.isFollowUp);

    return (
      <motion.div
        layout
        className={cn(
          "rounded-lg border p-4",
          isChild
            ? "border-amber-200 bg-amber-50/50"
            : "border-slate-100 bg-white",
          isDetail && (isChild ? "p-5" : "p-6"),
        )}
        initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        transition={{
          duration: 0.28,
          delay: animationDelay,
          ease: [0.22, 1, 0.36, 1],
        }}
      >
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <div
              className={cn(
                "flex items-center gap-2",
                isDetail ? "text-xs" : "text-[11px]",
              )}
            >
              <span
                className={cn(
                  showFollowUpBadge ? "text-amber-700" : "text-slate-500",
                )}
              >
                {label}
              </span>
              {showFollowUpBadge ? (
                <span
                  className={cn(
                    "inline-flex items-center rounded-full border border-amber-200 bg-amber-100 text-amber-700",
                    isDetail
                      ? "px-2.5 py-1 text-[11px]"
                      : "px-2 py-0.5 text-[10px]",
                  )}
                >
                  追问
                </span>
              ) : null}
            </div>
            <p
              className={cn(
                "font-medium text-slate-900",
                isDetail ? "text-lg leading-8" : "text-sm",
              )}
            >
              {item.question}
            </p>
          </div>
          {item.score !== null ? (
            <div
              className={cn(
                "shrink-0 text-indigo-500",
                isDetail ? "text-base" : "text-xs",
              )}
            >
              得分 {item.score}
            </div>
          ) : null}
        </div>

        <p
          className={cn(
            "mt-2 text-slate-500",
            isDetail ? "text-base leading-8" : "text-xs leading-6",
          )}
        >
          {item.answer}
        </p>

        {item.followUpNeeded ? (
          <p
            className={cn(
              "mt-2 text-amber-700",
              isDetail ? "text-sm" : "text-[11px]",
            )}
          >
            该轮回答触发了继续追问判定
          </p>
        ) : null}

        {feedback ? (
          <>
            <div className="mt-3 flex justify-end">
              <Button
                type="button"
                variant="ghost"
                size={isDetail ? "default" : "sm"}
                className={cn(
                  "rounded-full text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800",
                  isDetail ? "px-4 text-sm" : "h-7 px-3 text-xs",
                  isFeedbackVisible &&
                    "border border-emerald-200 bg-emerald-50 text-emerald-800",
                )}
                onClick={() => toggleFeedback(feedbackKey)}
              >
                {isFeedbackVisible ? "收起反馈" : "查看反馈"}
                {isFeedbackVisible ? (
                  <ChevronUp className="ml-1 h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="ml-1 h-3.5 w-3.5" />
                )}
              </Button>
            </div>
            <AnimatePresence initial={false}>
              {isFeedbackVisible ? (
                <motion.div
                  key={`${feedbackKey}-panel`}
                  className="overflow-hidden"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                >
                  <div
                    className={cn(
                      "mt-2 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-800",
                      isDetail
                        ? "px-4 py-3 text-sm leading-7"
                        : "px-3 py-2 text-xs leading-6",
                    )}
                  >
                    {feedback}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </>
        ) : null}
      </motion.div>
    );
  };

  return (
    <Card className={cn("border-slate-100", isDetail ? "p-8" : "p-6")}>
      <div className="flex items-center justify-between">
        <p
          className={cn(
            "font-medium text-slate-900",
            isDetail ? "text-xl" : "text-sm",
          )}
        >
          面试问答回放
        </p>
        {variant === "default" ? (
          reportSessionId ? (
            <Button
              asChild
              variant="outline"
              size="sm"
              className="rounded-full border-slate-900 bg-slate-900 text-white hover:bg-slate-800 hover:text-white"
            >
              <Link to={detailLink} state={{ sessionId: reportSessionId }}>
                <FileText className="mr-1.5 h-4 w-4" />
                详情复盘
              </Link>
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="rounded-full border-slate-900 bg-slate-900 text-white hover:bg-slate-800 hover:text-white"
              disabled
            >
              <FileText className="mr-1.5 h-4 w-4" />
              详情复盘
            </Button>
          )
        ) : null}
      </div>
      <div className="mt-4 space-y-4">
        {isRecordLoading ? (
          <div
            className={cn(
              "rounded-lg bg-slate-50 text-slate-500",
              isDetail ? "p-4 text-sm" : "p-3 text-xs",
            )}
          >
            正在加载问答回放...
          </div>
        ) : recordError ? (
          <div
            className={cn(
              "rounded-lg bg-rose-50 text-rose-600",
              isDetail ? "p-4 text-sm" : "p-3 text-xs",
            )}
          >
            {recordError}
          </div>
        ) : qaReviews.length > 0 ? (
          qaReplayGroups.map((group, groupIndex) => (
            <motion.div
              key={group.id}
              className={cn(
                "rounded-xl border border-slate-200",
                isDetail ? "p-5" : "p-4",
              )}
              initial={{ opacity: 0, y: 14, filter: "blur(5px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{
                duration: 0.32,
                delay: groupIndex * 0.06,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              {renderReviewItem({
                item: group.parent,
                label: resolveRoundLabel(group.parent, groupIndex),
                feedbackKey: `${group.id}::parent`,
                isChild: false,
              })}

              {group.followUps.length > 0 ? (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <div
                    className={cn(
                      "mb-3 inline-flex items-center rounded-full border border-amber-200 bg-amber-50 text-amber-700",
                      isDetail
                        ? "px-3 py-1.5 text-xs"
                        : "px-2.5 py-1 text-[11px]",
                    )}
                  >
                    追问链路（共 {group.followUps.length} 轮）
                  </div>
                  <div className="space-y-3">
                    {group.followUps.map((followUp, followUpIndex) =>
                      renderReviewItem({
                        item: followUp,
                        label: resolveRoundLabel(followUp, followUpIndex),
                        feedbackKey: `${group.id}::followup-${followUpIndex}`,
                        isChild: true,
                        animationDelay: followUpIndex * 0.05,
                      }),
                    )}
                  </div>
                </div>
              ) : null}
            </motion.div>
          ))
        ) : (
          <div
            className={cn(
              "rounded-lg bg-slate-50 text-slate-500",
              isDetail ? "p-4 text-sm" : "p-3 text-xs",
            )}
          >
            暂无问答回放数据
          </div>
        )}
      </div>
    </Card>
  );
}
