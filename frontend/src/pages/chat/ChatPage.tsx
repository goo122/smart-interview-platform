import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { toUserMessage } from "@/api/errors";
import type { ChatMessageResponse, CitationResponse, ConversationResponse } from "@/api/generated";
import { chatApi } from "@/features/chat/api";
import { chatKeys, useChatMutations, useConversationMessages, useConversations } from "@/features/chat/hooks";
import type { ChatPayload, ChatStreamCitation, ChatStreamEvent, UiMessage } from "@/features/chat/types";
import { KnowledgePanel } from "@/features/knowledge/components/KnowledgePanel";
import { useKnowledgeBaseReadiness } from "@/features/knowledge/hooks";

const newId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `request-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const asUiMessage = (message: ChatMessageResponse): UiMessage => ({
  id: message.id,
  conversationId: message.conversationId,
  role: message.role === "USER" || message.role === "SYSTEM" ? message.role : "ASSISTANT",
  content: message.content,
  status: message.status,
  sequence: message.sequence,
  requestId: message.requestId,
  citations: message.citations ?? [],
});

const normalizeCitation = (citation: ChatStreamCitation): CitationResponse => ({
  sourceId: citation.sourceId ?? citation.source_id ?? "",
  chunkId: citation.chunkId ?? citation.chunk_id ?? "",
  documentId: citation.documentId ?? citation.document_id ?? "",
  documentName: citation.documentName ?? citation.document_name ?? "未知文档",
  pageNumber: citation.pageNumber ?? citation.page_number ?? null,
  score: citation.score,
  excerpt: citation.excerpt ?? "",
});

export function ChatPage() {
  const queryClient = useQueryClient();
  const conversationsQuery = useConversations();
  const { create, finish, remove } = useChatMutations();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedSessionId = searchParams.get("sessionId");
  const [isNewConversation, setIsNewConversation] = useState(false);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<string | null>(null);
  const [topK, setTopK] = useState(5);
  const [liveMessages, setLiveMessages] = useState<Record<string, UiMessage[]>>({});
  const [streamingSessionId, setStreamingSessionId] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const activeRequestRef = useRef<{ sessionId: string; payload: ChatPayload; assistantId: string } | null>(null);
  const requestMapRef = useRef(new Map<string, { sessionId: string; payload: ChatPayload; assistantId: string }>());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversations = useMemo(() => conversationsQuery.data?.records ?? [], [conversationsQuery.data?.records]);
  const selectedSessionId = !isNewConversation && requestedSessionId && conversations.some((item) => item.sessionId === requestedSessionId)
    ? requestedSessionId
    : null;
  const selectedConversation = conversations.find((item) => item.sessionId === selectedSessionId) ?? null;
  const messagesQuery = useConversationMessages(selectedSessionId);
  const readiness = useKnowledgeBaseReadiness();
  const readyBaseIds = readiness.readyBaseIds;

  useEffect(() => {
    if (!conversationsQuery.data || isNewConversation) return;
    if (requestedSessionId && conversations.some((item) => item.sessionId === requestedSessionId)) return;
    if (conversations[0]?.sessionId) setSearchParams({ sessionId: conversations[0].sessionId }, { replace: true });
    else if (requestedSessionId) setSearchParams({}, { replace: true });
  }, [conversations, conversationsQuery.data, isNewConversation, requestedSessionId, setSearchParams]);

  const activeKnowledgeBaseId = selectedKnowledgeBaseId &&
    (!readiness.data || readyBaseIds.has(selectedKnowledgeBaseId))
    ? selectedKnowledgeBaseId
    : null;

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [selectedSessionId, liveMessages, messagesQuery.data]);

  const messages = useMemo(() => {
    const history = (messagesQuery.data ?? []).map(asUiMessage).sort((a, b) => a.sequence - b.sequence);
    const knownIds = new Set(history.map((message) => message.id));
    return [...history, ...(liveMessages[selectedSessionId ?? ""] ?? []).filter((message) => !knownIds.has(message.id))]
      .sort((a, b) => a.sequence - b.sequence);
  }, [liveMessages, messagesQuery.data, selectedSessionId]);

  const selectSession = (sessionId: string | null) => {
    if (streamingSessionId && streamingSessionId !== sessionId) controllerRef.current?.abort();
    setIsNewConversation(!sessionId);
    if (sessionId) setSearchParams({ sessionId }, { replace: true });
    else setSearchParams({}, { replace: true });
    setStreamError(null);
  };

  const updateLiveMessage = useCallback((sessionId: string, messageId: string, update: Partial<UiMessage>) => {
    setLiveMessages((current) => ({
      ...current,
      [sessionId]: (current[sessionId] ?? []).map((message) => message.id === messageId ? { ...message, ...update } : message),
    }));
  }, []);

  const appendLiveMessage = useCallback((sessionId: string, message: UiMessage) => {
    setLiveMessages((current) => ({ ...current, [sessionId]: [...(current[sessionId] ?? []), message] }));
  }, []);

  const handleEvent = useCallback((sessionId: string, clientAssistantId: string, event: ChatStreamEvent) => {
    const current = activeRequestRef.current;
    const assistantId = clientAssistantId;
    if (event.event === "start") {
      updateLiveMessage(sessionId, assistantId, { id: event.data.message_id, isStreaming: true });
      if (current) activeRequestRef.current = { ...current, assistantId: event.data.message_id };
    } else if (event.event === "delta") {
      setLiveMessages((state) => ({
        ...state,
        [sessionId]: (state[sessionId] ?? []).map((message) => message.id === assistantId || message.isStreaming
          ? { ...message, content: message.content + event.data.content, isStreaming: true }
          : message),
      }));
    } else if (event.event === "complete") {
      updateLiveMessage(sessionId, event.data.message_id || assistantId, {
        id: event.data.message_id || assistantId,
        content: event.data.content,
        status: "COMPLETED",
        isStreaming: false,
        citations: (event.data.citations ?? []).map(normalizeCitation),
      });
      setStreamingSessionId(null);
      void queryClient.invalidateQueries({ queryKey: chatKeys.messages(sessionId) });
      void queryClient.invalidateQueries({ queryKey: chatKeys.conversations() });
    } else if (event.event === "error") {
      updateLiveMessage(sessionId, current?.assistantId ?? assistantId, { status: "FAILED", isStreaming: false });
      setStreamError(event.data.message || "AI 回复失败，请稍后重试");
      setStreamingSessionId(null);
      void queryClient.invalidateQueries({ queryKey: chatKeys.messages(sessionId) });
    }
  }, [queryClient, updateLiveMessage]);

  const sendPayload = async (sessionId: string, payload: ChatPayload, existingAssistantId?: string) => {
    if (streamingSessionId || !payload.inputMessage?.trim()) return;
    const assistantId = existingAssistantId ?? `assistant-${payload.requestId}`;
    if (!existingAssistantId) {
      const sequence = messages.length + 1;
      appendLiveMessage(sessionId, {
        id: `user-${payload.requestId}`,
        conversationId: sessionId,
        role: "USER",
        content: payload.inputMessage.trim(),
        status: "COMPLETED",
        sequence,
        requestId: payload.requestId,
        citations: [],
      });
      appendLiveMessage(sessionId, {
        id: assistantId,
        conversationId: sessionId,
        role: "ASSISTANT",
        content: "",
        status: "PENDING",
        sequence: sequence + 1,
        requestId: payload.requestId,
        citations: [],
        isStreaming: true,
      });
    }
    setStreamError(null);
    setStreamingSessionId(sessionId);
    const controller = new AbortController();
    controllerRef.current = controller;
    activeRequestRef.current = { sessionId, payload, assistantId };
    if (payload.requestId) requestMapRef.current.set(payload.requestId, { sessionId, payload, assistantId });
    try {
      await chatApi.streamMessage(sessionId, payload, (event) => handleEvent(sessionId, assistantId, event), controller.signal);
    } catch (cause) {
      if ((cause as { name?: string }).name !== "AbortError") {
        updateLiveMessage(sessionId, activeRequestRef.current?.assistantId ?? assistantId, { status: "FAILED", isStreaming: false });
        setStreamError(toUserMessage(cause));
      } else {
        updateLiveMessage(sessionId, activeRequestRef.current?.assistantId ?? assistantId, { status: "STOPPED", stopped: true, isStreaming: false });
      }
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
      setStreamingSessionId(null);
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || streamingSessionId || isCreating) return;
    setInput("");
    let sessionId = selectedSessionId;
    if (!sessionId) {
      setIsCreating(true);
      try {
        const created = await create.mutateAsync({ title: text.slice(0, 80) });
        sessionId = created.sessionId;
        selectSession(sessionId);
      } catch (cause) {
        setStreamError(toUserMessage(cause));
        setIsCreating(false);
        return;
      } finally {
        setIsCreating(false);
      }
    }
    const requestId = newId();
    const payload: ChatPayload = {
      inputMessage: text,
      requestId,
      ...(activeKnowledgeBaseId ? { knowledgeBaseId: activeKnowledgeBaseId, topK } : {}),
    };
    await sendPayload(sessionId, payload);
  };

  const stop = () => controllerRef.current?.abort();

  const retry = async (message: UiMessage) => {
    if (!message.requestId || streamingSessionId) return;
    const request = requestMapRef.current.get(message.requestId);
    if (request) await sendPayload(request.sessionId, request.payload, message.id);
  };

  const handleDelete = async (conversation: ConversationResponse) => {
    if (!window.confirm(`确定删除会话“${conversation.title}”吗？`)) return;
    try {
      await remove.mutateAsync(conversation.sessionId);
      if (selectedSessionId === conversation.sessionId) selectSession(null);
    } catch (cause) {
      setStreamError(toUserMessage(cause));
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-topline">
        <div>
          <p className="eyebrow">YOUR PREPARATION SPACE</p>
          <h1>AI 对话</h1>
        </div>
        <div className="chat-mode-badge">{activeKnowledgeBaseId ? "RAG 知识库模式" : "普通对话"}</div>
      </div>
      <div className="chat-layout">
        <aside className="conversation-sidebar" aria-label="会话列表">
          <div className="sidebar-heading">
            <strong>会话</strong>
            <button type="button" className="button button-secondary" onClick={() => selectSession(null)}>+ 新建</button>
          </div>
          {conversationsQuery.isPending ? <p className="panel-muted">正在加载会话…</p> : null}
          {conversationsQuery.isError ? <div className="panel-error" role="alert"><span>{toUserMessage(conversationsQuery.error)}</span><button type="button" onClick={() => conversationsQuery.refetch()}>重试</button></div> : null}
          <div className="conversation-list">
            {conversations.map((conversation) => (
              <div className={`conversation-item ${conversation.sessionId === selectedSessionId ? "selected" : ""}`} key={conversation.sessionId}>
                <button type="button" onClick={() => selectSession(conversation.sessionId)}>
                  <strong>{conversation.title}</strong>
                  <small>{conversation.statusName === "FINISHED" ? "已结束" : "进行中"} · {conversation.messageCount ?? 0} 条消息</small>
                </button>
                <div className="conversation-actions">
                  {conversation.statusName !== "FINISHED" ? <button type="button" aria-label={`结束会话 ${conversation.title}`} onClick={() => finish.mutate(conversation.sessionId, { onError: (cause) => setStreamError(toUserMessage(cause)) })}>结束</button> : null}
                  <button type="button" aria-label={`删除会话 ${conversation.title}`} onClick={() => void handleDelete(conversation)}>×</button>
                </div>
              </div>
            ))}
            {!conversationsQuery.isPending && !conversations.length ? <p className="panel-muted">还没有会话，发送第一句话开始。</p> : null}
          </div>
        </aside>

        <section className="chat-main">
          <div className="chat-header">
            <div>
              <span className="chat-header-kicker">CURRENT CONVERSATION</span>
              <h2>{selectedConversation?.title ?? "新的对话"}</h2>
            </div>
            {activeKnowledgeBaseId ? <span className="rag-pill">⌁ RAG 已启用</span> : null}
          </div>
          <div className="message-list" aria-live="polite">
            {messagesQuery.isPending && selectedSessionId ? <div className="chat-empty">正在加载消息…</div> : null}
            {messagesQuery.isError ? <div className="chat-empty panel-error" role="alert">{toUserMessage(messagesQuery.error)}</div> : null}
            {!messages.length && !messagesQuery.isPending ? <div className="chat-empty"><strong>从一个问题开始</strong><span>你可以询问面试准备、技术概念，或让 AI 根据知识库回答。</span></div> : null}
            {messages.map((message) => <MessageBubble key={message.id} message={message} onRetry={() => void retry(message)} />)}
            <div ref={messagesEndRef} />
          </div>
          {streamError ? <div className="stream-error" role="alert">{streamError}</div> : null}
          <div className="chat-composer">
            <div className="composer-tools">
              <label className="knowledge-select-label">
                知识库
                <select
                  value={activeKnowledgeBaseId ?? ""}
                  onChange={(event) => setSelectedKnowledgeBaseId(event.target.value || null)}
                  disabled={!readiness.data?.records.some((base) => readyBaseIds.has(base.id))}
                >
                  <option value="">不使用（普通对话）</option>
                  {(readiness.data?.records ?? []).filter((base) => readyBaseIds.has(base.id)).map((base) => <option key={base.id} value={base.id}>{base.name}</option>)}
                </select>
              </label>
              {activeKnowledgeBaseId ? <label className="knowledge-select-label">引用数量<select value={topK} onChange={(event) => setTopK(Math.min(20, Math.max(1, Number(event.target.value))))}><option value={3}>3</option><option value={5}>5</option><option value={8}>8</option><option value={10}>10</option></select></label> : null}
            </div>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }}
              placeholder={selectedConversation?.statusName === "FINISHED" ? "会话已结束" : "输入你的问题，Enter 发送，Shift + Enter 换行"}
              disabled={selectedConversation?.statusName === "FINISHED" || Boolean(streamingSessionId)}
              rows={3}
            />
            <div className="composer-bottom"><small>{activeKnowledgeBaseId ? "回答将参考当前知识库中的 READY 文档" : "AI 会根据当前对话上下文回答"}</small>{streamingSessionId ? <button type="button" className="button button-stop" onClick={stop}>停止生成</button> : <button type="button" className="button button-primary" onClick={() => void send()} disabled={!input.trim() || Boolean(isCreating) || selectedConversation?.statusName === "FINISHED"}>{isCreating ? "创建中…" : "发送"}</button>}</div>
          </div>
        </section>
        <KnowledgePanel selectedBaseId={activeKnowledgeBaseId} onSelect={setSelectedKnowledgeBaseId} />
      </div>
    </div>
  );
}

function MessageBubble({ message, onRetry }: { message: UiMessage; onRetry: () => void }) {
  const isUser = message.role === "USER";
  return (
    <article className={`message-bubble ${isUser ? "user" : "assistant"}`}>
      <div className="message-meta"><span>{isUser ? "你" : "寻知 AI"}</span>{message.status === "PENDING" || message.isStreaming ? <span className="message-status">生成中…</span> : message.status === "STOPPED" ? <span className="message-status">已停止</span> : message.status === "FAILED" ? <span className="message-status">回复失败</span> : null}</div>
      <div className="message-content">{message.content || (message.isStreaming ? "…" : "")}</div>
      {!isUser && message.status === "FAILED" ? <button type="button" className="retry-link" onClick={onRetry}>重试</button> : null}
      {!isUser && message.citations?.length ? <CitationList citations={message.citations} /> : null}
    </article>
  );
}

function CitationList({ citations }: { citations: CitationResponse[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const ordered = [...citations].sort((a, b) => a.sourceId.localeCompare(b.sourceId, undefined, { numeric: true }));
  return <div className="citation-list"><small>参考来源</small>{ordered.map((citation) => <div className="citation" key={`${citation.sourceId}-${citation.chunkId}`}><button type="button" onClick={() => setExpanded(expanded === citation.sourceId ? null : citation.sourceId)}><strong>[{citation.sourceId}]</strong> {citation.documentName}{citation.pageNumber ? ` · 第 ${citation.pageNumber} 页` : ""}<span>{Math.round(citation.score * 100)}%</span></button>{expanded === citation.sourceId && citation.excerpt ? <p>{citation.excerpt}</p> : null}</div>)}</div>;
}
