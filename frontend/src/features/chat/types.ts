import type {
  ChatMessageResponse,
  ChatRequest,
  CitationResponse,
  ConversationResponse,
} from "@/api/generated";

export type ChatStreamCitation = CitationResponse & {
  source_id?: string;
  document_id?: string;
  document_name?: string;
  page_number?: number | null;
  chunk_id?: string;
};

export type ChatStreamEvent =
  | { event: "start"; data: { conversation_id: string; message_id: string } }
  | { event: "delta"; data: { content: string } }
  | { event: "complete"; data: { message_id: string; content: string; citations?: ChatStreamCitation[] } }
  | { event: "error"; data: { code: string; message: string } };

export type ChatMessage = ChatMessageResponse;

export type UiMessage = {
  id: string;
  conversationId: string;
  role: "USER" | "ASSISTANT" | "SYSTEM";
  content: string;
  status: string;
  sequence: number;
  requestId?: string | null;
  citations: CitationResponse[];
  isStreaming?: boolean;
  stopped?: boolean;
};

export type ChatPayload = Pick<ChatRequest, "inputMessage" | "requestId" | "knowledgeBaseId" | "topK">;
export type Conversation = ConversationResponse;
