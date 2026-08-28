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

// Frontend-safe DTO (apiKey/apiSecret removed)
export type AiProperty = Omit<AiPropertyEntity, "apiKey" | "apiSecret">;
export type AiPropertiesPageResult = PageResult<AiProperty>;

// Backend collection mapping: ai_conversation
export interface AiConversationEntity {
  _id?: string;
  sessionId: string;
  username: string;
  aiId: number;
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
  aiName?: string;
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
}

export interface GetAiPropertiesParams {
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
}

export interface StreamCallbacks {
  onMessage: (content: string) => void;
  onReasoning?: (content: string) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
}
