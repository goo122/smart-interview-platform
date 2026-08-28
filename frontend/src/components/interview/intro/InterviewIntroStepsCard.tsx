import { CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import InterviewRadarChart from "@/components/interview/report/InterviewRadarChart";
import type { RadarPoint } from "@/components/interview/report/types";

type InterviewIntroStepsCardProps = {
  title: string;
  steps: string[];
  updateTitle: string;
  updateDescription: string;
  sampleRadarTitle: string;
  mockRadarPoints: RadarPoint[];
};

export default function InterviewIntroStepsCard({
  title,
  steps,
  updateTitle,
  updateDescription,
  sampleRadarTitle,
  mockRadarPoints,
}: InterviewIntroStepsCardProps) {
  return (
    <Card className="border-slate-100 p-6">
      <div className="space-y-4">
        <p className="text-sm font-medium text-slate-900">{title}</p>
        <div className="space-y-3">
          {steps.map((step) => (
            <div key={step} className="flex items-center gap-3">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <p className="text-sm text-slate-600">{step}</p>
            </div>
          ))}
        </div>

        <Separator />

        <div className="space-y-2">
          <p className="text-xs text-slate-500">{updateTitle}</p>
          <p className="text-xs text-slate-400">{updateDescription}</p>
        </div>

        <div className="mt-4 rounded-xl border border-dashed border-slate-200 p-4 text-center">
          <p className="text-xs text-slate-500">{sampleRadarTitle}</p>
          <div className="mt-3 rounded-xl bg-slate-50/70 py-3">
            <InterviewRadarChart points={mockRadarPoints} />
          </div>
        </div>
      </div>
    </Card>
  );
}
