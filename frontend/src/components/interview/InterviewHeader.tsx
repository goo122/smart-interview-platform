import { NotebookPen, Video, VideoOff } from "lucide-react";
import { Button } from "@/components/ui/button";

type InterviewHeaderProps = {
  isReady: boolean;
  currentQuestionNumber: string | null;
  isCurrentQuestionFollowUp: boolean;
  currentFollowUpCount: number;
  isInterviewFinished: boolean;
  totalInterviewScore: number | null;
  isCameraOpen: boolean;
  isEndingInterview: boolean;
  onToggleCamera: () => void;
  onOpenSketchpad: () => void;
  onEndInterview: () => void;
};

export default function InterviewHeader({
  isReady,
  currentQuestionNumber,
  isCurrentQuestionFollowUp,
  currentFollowUpCount,
  isInterviewFinished,
  totalInterviewScore,
  isCameraOpen,
  isEndingInterview,
  onToggleCamera,
  onOpenSketchpad,
  onEndInterview,
}: InterviewHeaderProps) {
  return (
    <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white/70 px-6 py-4 backdrop-blur-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">
          Java 高级开发工程师模拟面试室
        </h2>
        <p className="text-sm text-slate-500">实时面试练习</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500">
          {isReady ? "面试进行中" : "待上传简历"}
        </div>
        {currentQuestionNumber && !isInterviewFinished ? (
          <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500">
            当前题号：{currentQuestionNumber}
          </div>
        ) : null}
        {isCurrentQuestionFollowUp && !isInterviewFinished ? (
          <div className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
            第 {currentFollowUpCount} 次追问
          </div>
        ) : null}
        {totalInterviewScore !== null ? (
          <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500">
            当前总分：{totalInterviewScore}
          </div>
        ) : null}
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenSketchpad}
            translate="no"
          >
            <NotebookPen className="mr-2 h-4 w-4" />
            构思板
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onToggleCamera}
            translate="no"
          >
            <Video
              aria-hidden={!isCameraOpen}
              className={isCameraOpen ? "mr-2 h-4 w-4" : "hidden"}
            />
            <VideoOff
              aria-hidden={isCameraOpen}
              className={isCameraOpen ? "hidden" : "mr-2 h-4 w-4"}
            />
            <span className={isCameraOpen ? "" : "hidden"}>关闭摄像头</span>
            <span className={isCameraOpen ? "hidden" : ""}>开启摄像头</span>
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={isEndingInterview}
            onClick={onEndInterview}
          >
            {isEndingInterview ? "处理中..." : "结束面试"}
          </Button>
        </div>
      </div>
    </div>
  );
}
