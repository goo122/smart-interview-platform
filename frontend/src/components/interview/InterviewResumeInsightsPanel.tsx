import ErrorNotice from "@/components/feedback/ErrorNotice";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

type InterviewResumeInsightsPanelProps = {
  resumeScore: number | null;
  resolvedInterviewTypeLabel: string;
  resumeSuggestions: string[];
  resumePreviewError: string | null;
  resumeOpenPreviewUrl: string | null;
  numPages: number;
};

export default function InterviewResumeInsightsPanel({
  resumeScore,
  resolvedInterviewTypeLabel,
  resumeSuggestions,
  resumePreviewError,
  resumeOpenPreviewUrl,
  numPages,
}: InterviewResumeInsightsPanelProps) {
  return (
    <div className="h-full space-y-4 overflow-y-auto">
      <Card className="border-slate-100 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-slate-900">简历得分</p>
          <span className="text-2xl font-semibold text-slate-900">
            {resumeScore ?? "--"}
          </span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {resumeScore === null
            ? "暂未返回简历评分"
            : "已根据简历内容完成评分"}
        </p>
      </Card>

      <Card className="space-y-3 border-slate-100 p-4">
        <p className="text-sm font-medium text-slate-900">面试岗位</p>
        <Separator />
        <div className="text-sm text-slate-700">
          {resolvedInterviewTypeLabel}
        </div>
      </Card>

      <Card className="space-y-3 border-slate-100 p-4">
        <p className="text-sm font-medium text-slate-900">简历建议</p>
        <Separator />
        <div className="space-y-2">
          {resumeSuggestions.length > 0 ? (
            resumeSuggestions.map((item, index) => (
              <div
                key={`${index}-${item}`}
                className="text-xs leading-6 text-slate-500"
              >
                {item}
              </div>
            ))
          ) : (
            <div className="text-xs text-slate-500">暂未返回简历建议</div>
          )}
        </div>
      </Card>

      {resumePreviewError ? (
        <ErrorNotice
          title="简历预览异常"
          description={`简历预览未能正常加载：${resumePreviewError}`}
        />
      ) : null}

      {resumeOpenPreviewUrl ? (
        <Button asChild variant="outline" className="w-full">
          <a href={resumeOpenPreviewUrl} target="_blank" rel="noreferrer">
            新窗口打开简历
          </a>
        </Button>
      ) : null}

      <div className="text-right text-xs text-slate-500">
        {resumePreviewError ? "页数解析失败" : `共 ${numPages} 页`}
      </div>
    </div>
  );
}
