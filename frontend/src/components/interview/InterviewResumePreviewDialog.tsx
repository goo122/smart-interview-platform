import InterviewResumeInsightsPanel from "@/components/interview/InterviewResumeInsightsPanel";
import InterviewResumePreviewContent from "@/components/interview/InterviewResumePreviewContent";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type InterviewResumePreviewDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  resumePreviewSource: File | string | undefined;
  resumePreviewError: string | null;
  resumeOpenPreviewUrl: string | null;
  numPages: number;
  resumeScore: number | null;
  resolvedInterviewTypeLabel: string;
  resumeSuggestions: string[];
  onLoadSuccess: (numPages: number) => void;
  onLoadError: (message: string) => void;
};

export default function InterviewResumePreviewDialog({
  open,
  onOpenChange,
  resumePreviewSource,
  resumePreviewError,
  resumeOpenPreviewUrl,
  numPages,
  resumeScore,
  resolvedInterviewTypeLabel,
  resumeSuggestions,
  onLoadSuccess,
  onLoadError,
}: InterviewResumePreviewDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[82vh] w-[92vw] max-w-6xl flex-col">
        <DialogHeader>
          <DialogTitle>简历预览</DialogTitle>
          <DialogDescription>
            这里会展示你上传的简历，以及系统提取出的面试方向和建议。
          </DialogDescription>
        </DialogHeader>

        <div className="grid flex-1 gap-4 overflow-hidden lg:grid-cols-[1fr_320px]">
          <InterviewResumePreviewContent
            resumePreviewSource={resumePreviewSource}
            resumePreviewError={resumePreviewError}
            resumeOpenPreviewUrl={resumeOpenPreviewUrl}
            numPages={numPages}
            onLoadSuccess={onLoadSuccess}
            onLoadError={onLoadError}
          />

          <InterviewResumeInsightsPanel
            resumeScore={resumeScore}
            resolvedInterviewTypeLabel={resolvedInterviewTypeLabel}
            resumeSuggestions={resumeSuggestions}
            resumePreviewError={resumePreviewError}
            resumeOpenPreviewUrl={resumeOpenPreviewUrl}
            numPages={numPages}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
