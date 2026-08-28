import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

type ErrorNoticeProps = {
  title: string;
  description?: string;
  className?: string;
};

export default function ErrorNotice({
  title,
  description,
  className,
}: ErrorNoticeProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700",
        className,
      )}
    >
      <AlertTriangle className="h-4 w-4 mt-0.5" />
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        {description && (
          <p className="text-xs text-red-600 mt-1">{description}</p>
        )}
      </div>
    </div>
  );
}
