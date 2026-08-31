import { forwardRef } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import CameraPreview, {
  type CameraPreviewHandle,
} from "@/components/camera/CameraPreview";
import ErrorNotice from "@/components/feedback/ErrorNotice";
import type { InterviewDemeanorEvaluationResult } from "@/services/interviewService";
import type { MediaError } from "@/lib/media";
import type { DemeanorPollingStatus } from "@/hooks/interview/camera/useInterviewDemeanorPolling";
import { cn } from "@/lib/utils";

type CameraErrorCopy = {
  title: string;
  description: string;
} | null;

type InterviewCameraOverlayProps = {
  isCameraExpanded: boolean;
  cameraErrorCopy: CameraErrorCopy;
  onCameraError: (error: MediaError) => void;
  onToggleExpanded: () => void;
  demeanorStatus: DemeanorPollingStatus;
  latestDemeanorEvaluation: InterviewDemeanorEvaluationResult | null;
};

const InterviewCameraOverlay = forwardRef<
  CameraPreviewHandle,
  InterviewCameraOverlayProps
>(function InterviewCameraOverlay(
  {
    isCameraExpanded,
    cameraErrorCopy,
    onCameraError,
    onToggleExpanded,
    demeanorStatus,
    latestDemeanorEvaluation,
  }: InterviewCameraOverlayProps,
  ref,
) {
  return (
    <Card
      className={cn(
        "absolute overflow-hidden border-2 bg-black shadow-2xl transition-all duration-300",
        isCameraExpanded
          ? "bottom-24 left-4 right-4 top-4 z-20"
          : "right-4 top-4 z-20 h-48 w-64",
      )}
    >
      <div className="group relative h-full w-full">
        <CameraPreview
          ref={ref}
          isOpen
          onError={onCameraError}
        />
        {cameraErrorCopy && (
          <div className="absolute inset-3 z-10">
            <ErrorNotice
              title={cameraErrorCopy.title}
              description={cameraErrorCopy.description}
            />
          </div>
        )}
        <div className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-black/50 text-white hover:bg-black/70"
            onClick={onToggleExpanded}
          >
            {isCameraExpanded ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-4 w-4" />
            )}
          </Button>
        </div>
        <div className="absolute bottom-2 left-2 right-2 rounded-md bg-black/60 px-2 py-1.5">
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                demeanorStatus === "analyzing" && "animate-pulse bg-red-500",
                demeanorStatus === "completed" && "bg-emerald-400",
                demeanorStatus === "unavailable" && "bg-slate-400",
                demeanorStatus === "error" && "bg-amber-400",
                (demeanorStatus === "idle" || demeanorStatus === "checking") &&
                  "bg-slate-300",
              )}
            />
            <span className="truncate text-xs font-medium text-white drop-shadow-md">
              {demeanorStatus === "checking" && "正在检查仪态分析服务..."}
              {demeanorStatus === "analyzing" && "正在分析可观察的面试表现..."}
              {demeanorStatus === "completed" &&
                `仪态表达 ${latestDemeanorEvaluation?.overallScore ?? "--"} 分`}
              {demeanorStatus === "unavailable" && "仪态分析未启用"}
              {demeanorStatus === "error" && "本次仪态分析失败，面试可继续"}
              {demeanorStatus === "idle" && "仪态分析已暂停"}
            </span>
          </div>
          {demeanorStatus === "completed" && latestDemeanorEvaluation && (
            <div className="mt-1 space-y-0.5 text-[10px] leading-4 text-white/80">
              <p className="truncate">{latestDemeanorEvaluation.summary}</p>
              <p className="truncate">
                建议：{latestDemeanorEvaluation.suggestions[0] ?? "保持自然表达"}
              </p>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
});

export default InterviewCameraOverlay;
