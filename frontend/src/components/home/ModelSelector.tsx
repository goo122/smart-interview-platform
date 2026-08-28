import { useState } from "react";
import { Check, ChevronDown, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { AiProperty } from "@/types/ai";

interface ModelSelectorProps {
  models: AiProperty[];
  selectedModel: AiProperty | null;
  onSelect: (model: AiProperty) => void;
}

export function ModelSelector({
  models,
  selectedModel,
  onSelect,
}: ModelSelectorProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          role="combobox"
          aria-expanded={open}
          className="gap-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 px-3 h-9"
        >
          <Sparkles className="w-4 h-4 text-slate-500" />
          <span className="text-sm font-medium">
            {selectedModel ? selectedModel.aiName : "加载中..."}
          </span>
          <ChevronDown className="w-3 h-3 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-1" align="start">
        <div className="space-y-1">
          {models.map((model) => (
            <Button
              key={model.id}
              variant="ghost"
              className={cn(
                "w-full justify-start font-normal px-2 h-8",
                selectedModel?.id === model.id &&
                  "bg-slate-100 text-indigo-600",
              )}
              onClick={() => {
                onSelect(model);
                setOpen(false);
              }}
            >
              <span className="truncate flex-1 text-left">{model.aiName}</span>
              {selectedModel?.id === model.id && (
                <Check className="ml-2 h-3 w-3" />
              )}
            </Button>
          ))}
          {models.length === 0 && (
            <div className="p-2 text-xs text-center text-slate-400">
              暂无可用模型
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
