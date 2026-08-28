import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ChatMessageContentProps = {
  content: string;
  isStreaming: boolean;
  showStreamingCursor: boolean;
};

export default function ChatMessageContent({
  content,
  isStreaming,
  showStreamingCursor,
}: ChatMessageContentProps) {
  return (
    <div className="leading-relaxed">
      <div className="prose prose-sm dark:prose-invert max-w-none break-words">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
      {isStreaming && showStreamingCursor ? (
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{
            repeat: Infinity,
            duration: 0.8,
            ease: "easeInOut",
          }}
          className="inline-block w-2 h-4 bg-slate-400 ml-1 align-middle"
        />
      ) : null}
    </div>
  );
}
