// AUTO-GENERATED from backend FastAPI OpenAPI. Do not edit manually.

export interface components {
  schemas: {
    LoginRequest: {
      "account": string;
      "password": string;
    };
    MessageResponse: {
      "message": string;
    };
    RefreshRequest: {
      "refresh_token": string;
    };
    RegisterRequest: {
      "username": string;
      "email": string;
      "password": string;
    };
    TokenResponse: {
      "access_token": string;
      "refresh_token": string;
      "token_type": "bearer";
      "expires_in": number;
    };
    UserResponse: {
      "id": string;
      "username": string;
      "email": string;
      "is_active": boolean;
      "created_at": string;
      "updated_at": string;
    };
    KnowledgeBaseCreateRequest: {
      "name": string;
      "description"?: string | null;
    };
    KnowledgeBaseResponse: {
      "id": string;
      "user_id": string;
      "name": string;
      "description": string | null;
      "created_at": string;
      "updated_at": string;
    };
    KnowledgeDocumentResponse: {
      "id": string;
      "knowledge_base_id": string;
      "original_filename": string;
      "safe_filename": string;
      "content_type": string;
      "size_bytes": number;
      "sha256": string;
      "status": string;
      "page_count": number;
      "chunk_count": number;
      "error_code": string | null;
      "error_message": string | null;
      "created_at": string;
      "updated_at": string;
      "completed_at": string | null;
    };
    KnowledgeBasePage: {
      "records": Array<components["schemas"]["KnowledgeBaseResponse"]>;
      "total": number;
      "size": number;
      "current": number;
      "pages": number;
    };
    KnowledgeDocumentPage: {
      "records": Array<components["schemas"]["KnowledgeDocumentResponse"]>;
      "total": number;
      "size": number;
      "current": number;
      "pages": number;
    };
    ChatRequest: {
      "sessionId"?: string | null;
      "inputMessage"?: string | null;
      "content"?: string | null;
      "userName"?: string | null;
      "aiId"?: number | null;
      "messageSeq"?: number | null;
      "requestId"?: string | null;
      "imageUrls"?: Array<string> | null;
      "mediaList"?: Array<unknown> | null;
      "fileUrls"?: Array<string> | null;
      "knowledgeBaseId"?: string | null;
      "topK"?: number | null;
      "similarityThreshold"?: number | null;
    };
    CreateConversationRequest: {
      "userName"?: string | null;
      "firstMessage"?: string | null;
      "aiId"?: number | null;
      "title"?: string | null;
      "modelName"?: string | null;
    };
    CreateConversationResponse: {
      "sessionId": string;
      "conversationTitle": string;
      "id": string;
      "title": string;
    };
    ConversationResponse: {
      "id": string;
      "user_id": string;
      "title": string;
      "status": number;
      "statusName": string;
      "modelName"?: string | null;
      "createdAt": string;
      "updatedAt": string;
      "finishedAt"?: string | null;
      "sessionId": string;
      "username"?: string | null;
      "aiId"?: number | null;
      "aiName"?: string | null;
      "messageCount"?: number;
      "lastMessageTime"?: string | null;
      "createTime": string;
      "updateTime": string;
    };
    ChatMessageResponse: {
      "id": string;
      "conversationId": string;
      "role": string;
      "content": string;
      "status": string;
      "sequence": number;
      "requestId"?: string | null;
      "errorMessage"?: string | null;
      "createdAt": string;
      "completedAt"?: string | null;
      "sessionId": string;
      "messageType": number;
      "messageContent": string;
      "messageSeq": number;
      "responseTime"?: number | null;
      "tokenCount"?: number | null;
      "citations"?: Array<components["schemas"]["CitationResponse"]>;
    };
    CitationResponse: {
      "sourceId": string;
      "chunkId": string;
      "documentId": string;
      "documentName": string;
      "pageNumber"?: number | null;
      "score": number;
      "excerpt": string;
    };
    ConversationPage: {
      "records": Array<components["schemas"]["ConversationResponse"]>;
      "total": number;
      "size": number;
      "current": number;
      "pages": number;
    };
    ChatHistoryPage: {
      "records": Array<components["schemas"]["ChatMessageResponse"]>;
      "total": number;
      "size": number;
      "current": number;
      "pages": number;
    };
    DeleteResponse: {
      "message"?: string;
    };
    EmptyResponse: {
      "message": string;
    };
  };
}

export type LoginRequest = components["schemas"]["LoginRequest"];
export type MessageResponse = components["schemas"]["MessageResponse"];
export type RefreshRequest = components["schemas"]["RefreshRequest"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserResponse = components["schemas"]["UserResponse"];
export type KnowledgeBaseCreateRequest = components["schemas"]["KnowledgeBaseCreateRequest"];
export type KnowledgeBaseResponse = components["schemas"]["KnowledgeBaseResponse"];
export type KnowledgeDocumentResponse = components["schemas"]["KnowledgeDocumentResponse"];
export type KnowledgeBasePage = components["schemas"]["KnowledgeBasePage"];
export type KnowledgeDocumentPage = components["schemas"]["KnowledgeDocumentPage"];
export type ChatRequest = components["schemas"]["ChatRequest"];
export type CreateConversationRequest = components["schemas"]["CreateConversationRequest"];
export type CreateConversationResponse = components["schemas"]["CreateConversationResponse"];
export type ConversationResponse = components["schemas"]["ConversationResponse"];
export type ChatMessageResponse = components["schemas"]["ChatMessageResponse"];
export type CitationResponse = components["schemas"]["CitationResponse"];
export type ConversationPage = components["schemas"]["ConversationPage"];
export type ChatHistoryPage = components["schemas"]["ChatHistoryPage"];
export type DeleteResponse = components["schemas"]["DeleteResponse"];
export type EmptyResponse = components["schemas"]["EmptyResponse"];
