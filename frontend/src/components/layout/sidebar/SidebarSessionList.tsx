import { Button } from "@/components/ui/button";
import type { AiConversation } from "@/types/ai";

type SidebarSessionListProps = {
  conversations: AiConversation[];
  activePathname: string;
  hasNextPage: boolean | undefined;
  isFetchingNextPage: boolean;
  onOpenSession: (sessionId: string) => void;
};

export default function SidebarSessionList({
  conversations,
  activePathname,
  hasNextPage,
  isFetchingNextPage,
  onOpenSession,
}: SidebarSessionListProps) {
  return (
    <>
      {conversations.map((conversation) => (
        <Button
          key={conversation.sessionId}
          variant={
            activePathname.includes(conversation.sessionId)
              ? "secondary"
              : "ghost"
          }
          className="w-full justify-start text-left h-auto py-2 px-3 font-normal rounded-xl mb-1 hover:bg-slate-100"
          onClick={() => onOpenSession(conversation.sessionId)}
        >
          <div className="flex flex-col gap-0.5 overflow-hidden w-full">
            <span className="truncate text-sm text-slate-700 font-medium">
              {conversation.title || "无标题会话"}
            </span>
            <span className="text-[10px] text-slate-400 truncate">
              {conversation.createTime
                ? new Date(conversation.createTime).toLocaleDateString()
                : "Unknown date"}{" "}
              · {conversation.aiName || "Unknown model"}
            </span>
          </div>
        </Button>
      ))}

      {isFetchingNextPage ? (
        <div className="text-center py-2 text-xs text-slate-400">加载中...</div>
      ) : null}

      {!hasNextPage && conversations.length > 0 ? (
        <div className="text-center py-2 text-xs text-slate-300">
          没有更多了
        </div>
      ) : null}

      {!isFetchingNextPage && conversations.length === 0 ? (
        <div className="text-center py-4 text-xs text-slate-400">
          暂无会话记录
        </div>
      ) : null}
    </>
  );
}
