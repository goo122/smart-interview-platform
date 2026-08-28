import { forwardRef } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import CameraPreview, {
  type CameraPreviewHandle,
} from "@/components/camera/CameraPreview";
import ErrorNotice from "@/components/feedback/ErrorNotice";
import type { MediaError } from "@/lib/media";
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
        <div className="absolute bottom-3 left-3 flex items-center gap-2">
          <div className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
          <span className="text-xs font-medium text-white drop-shadow-md">
            正在分析状态...
          </span>
        </div>
      </div>
    </Card>
  );
});

export default InterviewCameraOverlay;
