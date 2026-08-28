import { useState } from "react";
import { Brain, ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

type ChatReasoningPanelProps = {
  reasoning: string;
  isStreaming: boolean;
  hasContent: boolean;
};

export default function ChatReasoningPanel({
  reasoning,
  isStreaming,
  hasContent,
}: ChatReasoningPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="border rounded-lg bg-slate-50 overflow-hidden">
      <button
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex items-center w-full px-3 py-2 text-xs text-slate-500 hover:bg-slate-100 transition-colors"
      >
        <Brain className="w-3.5 h-3.5 mr-2" />
        <span className="font-medium">深度思考</span>
        <motion.div
          animate={{ rotate: isExpanded ? 90 : 0 }}
          transition={{ duration: 0.2 }}
          className="ml-auto"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {isExpanded ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-3 pb-3 pt-0 text-sm text-slate-500 italic whitespace-pre-wrap border-t border-slate-100/50">
              <div className="pt-2">
                {reasoning}
                {isStreaming && !hasContent ? (
                  <span className="inline-block w-1.5 h-3 bg-slate-400 ml-1 animate-pulse align-middle" />
                ) : null}
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
