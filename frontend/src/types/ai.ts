import type { AiPropertyResponse } from "@/api/generated";

export interface PageResult<T> {
  records: T[];
  total: number;
  size: number;
  current: number;
  pages: number;
}

// Backend table mapping: ai_properties (includes sensitive fields)
export interface AiPropertyEntity {
  id: number;
  aiName: string;
  aiType: string;
  apiKey?: string | null;
  apiSecret?: string | null;
  apiUrl?: string | null;
  modelName?: string | null;
  maxTokens?: number | null;
  temperature?: number | string | null;
  systemPrompt?: string | null;
  isEnabled?: 0 | 1 | null;
  enableThinking?: 0 | 1 | null;
  thinkingBudgetTokens?: number | null;
  createTime?: string | null;
  updateTime?: string | null;
  delFlag?: 0 | 1 | null;
  projectId?: string | null;
  organizationId?: string | null;
}

// Frontend-safe DTO generated from the backend response schema. Sensitive
// provider configuration is intentionally not part of the model selector type.
export type AiProperty = AiPropertyResponse;
export type AiPropertiesPageResult = PageResult<AiProperty>;

// Backend collection mapping: ai_conversation
export interface AiConversationEntity {
  _id?: string;
  sessionId: string;
  username: string;
  aiId?: number | null;
  modelName?: string | null;
  title?: string;
  status: number; // 1=in progress, 2=finished
  messageCount?: number;
  lastMessageTime?: string;
  createTime?: string;
  updateTime?: string;
  delFlag?: number;
  _class?: string;
}

export type AiConversation = AiConversationEntity & {
  aiName?: string | null;
};

export type AiConversationsPageResult = PageResult<AiConversation>;

// Backend collection mapping: ai_message
export interface AiMessageEntity {
  _id?: string;
  id?: string;
  sessionId: string;
  messageType: number; // 1=user, 2=assistant
  messageContent: string;
  messageSeq: number;
  reasoningContent?: string;
  responseTime?: number;
  tokenCount?: number;
  errorMessage?: string;
  createTime?: string;
  updateTime?: string;
  delFlag?: number;
  _class?: string;
}

export type AiMessageHistory = AiMessageEntity & { id: string };

export interface AiCitation {
  sourceId?: string;
  source_id?: string;
  chunkId?: string;
  chunk_id?: string;
  documentId?: string;
  document_id?: string;
  documentName?: string;
  document_name?: string;
  pageNumber?: number | null;
  page_number?: number | null;
  score?: number;
  excerpt?: string;
}

export type AiMessageHistoryWithCitations = AiMessageHistory & {
  citations?: AiCitation[];
};

export type AiMessageHistoryListResult = AiMessageHistory[];
export type AiMessageHistoryPageResult = PageResult<AiMessageHistory>;

// Backend table mapping: ai_message_media
export interface AiMessageMediaEntity {
  id: number;
  sessionId: string;
  messageSeq: number;
  mediaType: "image" | "file" | "audio" | string;
  mediaUrl: string;
  fileName?: string | null;
  fileSize?: number | null;
  contentType?: string | null;
  createTime?: string | null;
}

export type AiMessageMediaDTO = AiMessageMediaEntity;

// Backend table mapping: agent_tag
export interface AgentTagEntity {
  id: number;
  tagName: string;
  agentId: number;
  description?: string | null;
  createTime?: string | null;
  updateTime?: string | null;
  delFlag?: 0 | 1 | null;
}

export type AgentTagDTO = AgentTagEntity;

export interface CreateConversationResult {
  sessionId: string;
  conversationTitle: string;
}

export type CreateConversationResponse = CreateConversationResult;

export interface CreateConversationParams {
  userName: string;
  firstMessage?: string;
  aiId?: number;
  modelName?: string;
}

export interface GetAiPropertiesParams {
  current?: number;
  size?: number;
  isEnabled?: number;
}

export interface GetConversationsParams {
  current?: number;
  size?: number;
  aiId?: number;
  status?: number;
  title?: string;
  username?: string;
}

export interface GetHistoryMessagesPageParams {
  sessionId?: string;
  current: number;
  size: number;
  username?: string;
}

export interface AiMessageMediaReqDTO {
  mediaType: string;
  mediaUrl: string;
  fileName?: string;
  fileSize?: number;
  contentType?: string;
}

export interface ChatStreamParams {
  sessionId: string;
  inputMessage: string;
  userName: string;
  aiId?: number;
  messageSeq?: number;
  imageUrls?: string[];
  mediaList?: AiMessageMediaReqDTO[];
  requestId?: string;
  knowledgeBaseId?: string | null;
  topK?: number;
  similarityThreshold?: number;
}

export interface StreamCallbacks {
  onMessage: (content: string) => void;
  onReasoning?: (content: string) => void;
  onDone?: () => void;
  onComplete?: (data: { content?: string; citations?: AiCitation[] }) => void;
  onError?: (error: Error) => void;
}
