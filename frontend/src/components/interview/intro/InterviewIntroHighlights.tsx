import { Card } from "@/components/ui/card";
import type { IntroHighlight } from "@/components/interview/intro/introCopy";

type InterviewIntroHighlightsProps = {
  highlights: IntroHighlight[];
};

export default function InterviewIntroHighlights({
  highlights,
}: InterviewIntroHighlightsProps) {
  return (
    <div className="grid sm:grid-cols-2 gap-4">
      {highlights.map((highlight) => (
        <Card key={highlight.title} className="p-4 border-slate-100">
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-900">
              {highlight.title}
            </p>
            <p className="text-xs text-slate-500">{highlight.description}</p>
          </div>
        </Card>
      ))}
    </div>
  );
}
