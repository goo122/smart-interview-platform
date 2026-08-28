import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/lib/constants";

export default function InterviewReportHeader() {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">面试表现报告</h1>
        <p className="text-sm text-slate-500">综合评估 · 结果可用于后续训练</p>
      </div>
      <div className="flex gap-2">
        <Button
          asChild
          variant="outline"
          className="rounded-full border-slate-900 bg-slate-900 text-white hover:bg-slate-800 hover:text-white"
        >
          <Link to={ROUTES.interviewIntro}>重新面试</Link>
        </Button>
      </div>
    </div>
  );
}
