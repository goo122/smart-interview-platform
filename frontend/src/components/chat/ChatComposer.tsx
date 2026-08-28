import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";

type ChatComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend?: () => void;
  placeholder?: string;
  disabled?: boolean;
  leading?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
};

export default function ChatComposer({
  value,
  onChange,
  onSend,
  placeholder,
  disabled,
  leading,
  actions,
  className,
}: ChatComposerProps) {
  return (
    <div
      className={cn(
        "relative flex items-center gap-3 bg-white px-4 py-3 rounded-3xl border border-slate-200 shadow-sm focus-within:ring-2 focus-within:ring-slate-200 transition-all",
        className,
      )}
    >
      {leading}
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend?.();
          }
        }}
        placeholder={placeholder}
        className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 px-0 py-1 h-auto min-h-[28px] max-h-32 resize-none text-sm"
        disabled={disabled}
      />
      {actions}
    </div>
  );
}
