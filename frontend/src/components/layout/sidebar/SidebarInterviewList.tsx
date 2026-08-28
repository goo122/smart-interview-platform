import { Button } from "@/components/ui/button";
import type { InterviewRecordResult } from "@/services/interviewService";
import { ROUTES } from "@/lib/constants";

type SidebarInterviewListProps = {
  records: InterviewRecordResult[];
  activePathname: string;
  activeSessionId: string | null;
  hasNextPage: boolean | undefined;
  isFetchingNextPage: boolean;
  onOpenRecord: (sessionId: string) => void;
};

const formatDate = (value?: string | null) => {
  if (!value) return "Unknown date";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
};

const formatScore = (value?: number | null) => {
  if (typeof value !== "number" || Number.isNaN(value)) return "--";
  return String(value);
};

export default function SidebarInterviewList({
  records,
  activePathname,
  activeSessionId,
  hasNextPage,
  isFetchingNextPage,
  onOpenRecord,
}: SidebarInterviewListProps) {
  return (
    <>
      {records.map((record) => {
        const isActive =
          activePathname.startsWith(ROUTES.interviewReport) &&
          activeSessionId === record.sessionId;

        return (
          <Button
            key={record.sessionId}
            variant={isActive ? "secondary" : "ghost"}
            className="mb-1 h-auto w-full justify-start rounded-xl px-3 py-2 text-left font-normal hover:bg-slate-100"
            onClick={() => onOpenRecord(record.sessionId)}
          >
            <div className="flex w-full flex-col gap-0.5 overflow-hidden">
              <span className="truncate text-sm font-medium text-slate-700">
                {record.interviewDirection || "面试记录"}
              </span>
              <span className="truncate text-[10px] text-slate-400">
                {formatDate(record.startTime || record.createTime)} · 得分{" "}
                {formatScore(record.interviewScore)}
              </span>
            </div>
          </Button>
        );
      })}

      {isFetchingNextPage ? (
        <div className="py-2 text-center text-xs text-slate-400">加载中...</div>
      ) : null}

      {!hasNextPage && records.length > 0 ? (
        <div className="py-2 text-center text-xs text-slate-300">
          没有更多了
        </div>
      ) : null}

      {!isFetchingNextPage && records.length === 0 ? (
        <div className="py-4 text-center text-xs text-slate-400">
          暂无面试记录
        </div>
      ) : null}
    </>
  );
}
