import { Loader2 } from "lucide-react";

export default function ChatHistoryLoadingOverlay() {
  return (
    <div className="absolute inset-0 z-20 pointer-events-none flex items-center justify-center">
      <div className="rounded-2xl border border-slate-200 bg-white/90 backdrop-blur px-4 py-3 shadow-sm">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
          <span>正在加载会话历史...</span>
        </div>
      </div>
    </div>
  );
}
