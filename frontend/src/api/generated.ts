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
    AiPropertyResponse: {
      "id": number;
      "aiName": string;
      "aiType": string;
      "modelName"?: string | null;
      "isEnabled": number;
      "enableThinking": number;
    };
    AiPropertiesPage: {
      "records": Array<components["schemas"]["AiPropertyResponse"]>;
      "total": number;
      "size": number;
      "current": number;
      "pages": number;
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
    InterviewType: "TECHNICAL" | "BEHAVIORAL" | "MIXED";
    InterviewDifficulty: "EASY" | "MEDIUM" | "HARD";
    CreateInterviewSessionRequest: {
      "knowledgeBaseId": string;
      "jobTitle": string;
      "jobDescription": string;
      "interviewType"?: components["schemas"]["InterviewType"];
      "difficulty"?: components["schemas"]["InterviewDifficulty"];
      "questionCount"?: number;
      "requestId"?: string | null;
    };
    ResolveInterviewRoleRequest: {
      "knowledgeBaseId": string;
    };
    ResolveInterviewRoleResponse: {
      "jobTitle": string;
      "jobDescription": string;
      "confidence"?: number | null;
      "inferred": boolean;
      "inferenceVersion": string;
    };
    InterviewSessionResponse: {
      "id": string;
      "sessionId": string;
      "userId": string;
      "knowledgeBaseId": string;
      "jobTitle": string;
      "interviewType": string;
      "difficulty": string;
      "questionCount": number;
      "status": string;
      "currentQuestionIndex": number;
      "preparationProgress": number;
      "canStart": boolean;
      "version": number;
      "requestId"?: string | null;
      "failureCode"?: string | null;
      "failureMessage"?: string | null;
      "createdAt": string;
      "updatedAt": string;
      "preparedAt"?: string | null;
      "startedAt"?: string | null;
      "finishedAt"?: string | null;
      "resumeScore"?: number | null;
      "resumeEvaluationStatus"?: string | null;
      "resumeEvaluation"?: components["schemas"]["ResumeEvaluationResponse"] | null;
    };
    ResumeEvaluationResponse: {
      "status": string;
      "overallScore"?: number | null;
      "skillsMatchScore"?: number | null;
      "experienceMatchScore"?: number | null;
      "evidenceQualityScore"?: number | null;
      "clarityScore"?: number | null;
      "strengths": Array<string>;
      "gaps": Array<string>;
      "suggestions": Array<string>;
      "summary"?: string | null;
      "evaluationVersion": string;
      "evaluatedAt"?: string | null;
      "failureCode"?: string | null;
    };
    InterviewQuestionResponse: {
      "id": string;
      "sessionId": string;
      "sequence": number;
      "content": string;
      "category": string;
      "difficulty": string;
      "expectedPoints": Array<string>;
      "sourceSummary"?: string | null;
      "createdAt": string;
      "citations"?: Array<components["schemas"]["InterviewQuestionCitationResponse"]>;
    };
    InterviewQuestionCitationResponse: {
      "id": string;
      "questionId": string;
      "chunkId": string;
      "documentId": string;
      "sourceId": string;
      "pageNumber"?: number | null;
      "score": number;
      "excerpt": string;
      "ordinal": number;
      "createdAt": string;
    };
    InterviewEvaluationResponse: {
      "id": string;
      "turnId": string;
      "overallScore": number;
      "technicalScore": number;
      "relevanceScore": number;
      "clarityScore": number;
      "depthScore": number;
      "strengths": Array<string>;
      "weaknesses": Array<string>;
      "feedback": string;
      "suggestedImprovements": Array<string>;
      "shouldFollowUp": boolean;
      "followUpFocus"?: string | null;
      "followUpQuestion"?: string | null;
      "createdAt": string;
    };
    InterviewTurnResponse: {
      "turnId": string;
      "sessionId": string;
      "questionId"?: string | null;
      "parentTurnId"?: string | null;
      "turnType": string;
      "question": string;
      "sequence": number;
      "followUpDepth": number;
      "status": string;
      "canAnswer": boolean;
      "answer"?: string | null;
      "answerRequestId"?: string | null;
      "answeredAt"?: string | null;
      "evaluation"?: components["schemas"]["InterviewEvaluationResponse"] | null;
      "createdAt": string;
      "evaluatedAt"?: string | null;
    };
    SubmitInterviewAnswerRequest: {
      "turnId": string;
      "answer": string;
      "requestId": string;
    };
    SubmitInterviewAnswerResponse: {
      "sessionId": string;
      "turnId": string;
      "status": string;
      "requestId": string;
    };
    InterviewSessionPage: {
      "records": Array<components["schemas"]["InterviewSessionResponse"]>;
      "total": number;
      "size": number;
      "current": number;
      "pages": number;
    };
    InterviewReportItemResponse: {
      "id": string;
      "turnId": string;
      "parentTurnId"?: string | null;
      "sequence": number;
      "turnType": string;
      "question": string;
      "answer": string;
      "scores": Record<string, unknown>;
      "strengths": Array<string>;
      "weaknesses": Array<string>;
      "feedback": string;
      "suggestedImprovements": Array<string>;
      "sources": Array<Record<string, unknown>>;
      "createdAt": string;
    };
    InterviewReportResponse: {
      "reportId": string;
      "sessionId": string;
      "status": string;
      "jobTitle": string;
      "interviewType": string;
      "difficulty": string;
      "overallScore": number;
      "dimensionScores": Record<string, unknown>;
      "radarData": Array<Record<string, unknown>>;
      "summary": string;
      "strengths": Array<string>;
      "weaknesses": Array<string>;
      "suggestedImprovements": Array<string>;
      "actionPlan": Array<string>;
      "recommendedLevel"?: string | null;
      "items": Array<components["schemas"]["InterviewReportItemResponse"]>;
      "aggregationVersion": string;
      "generatedBy": string;
      "createdAt": string;
      "updatedAt": string;
      "completedAt"?: string | null;
      "failureCode"?: string | null;
      "failureMessage"?: string | null;
      "resumeScore"?: number | null;
      "resumeEvaluation"?: components["schemas"]["ResumeEvaluationSnapshotResponse"] | null;
    };
    ResumeEvaluationSnapshotResponse: {
      "status": string;
      "overallScore"?: number | null;
      "skillsMatchScore"?: number | null;
      "experienceMatchScore"?: number | null;
      "evidenceQualityScore"?: number | null;
      "clarityScore"?: number | null;
      "strengths": Array<string>;
      "gaps": Array<string>;
      "suggestions": Array<string>;
      "summary"?: string | null;
      "evaluationVersion": string;
      "providerName"?: string | null;
      "evaluatedAt"?: string | null;
      "failureCode"?: string | null;
    };
    InterviewReportPage: {
      "records": Array<components["schemas"]["InterviewReportResponse"]>;
      "total": number;
      "size": number;
      "current": number;
      "pages": number;
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
export type AiPropertyResponse = components["schemas"]["AiPropertyResponse"];
export type AiPropertiesPage = components["schemas"]["AiPropertiesPage"];
export type CreateConversationRequest = components["schemas"]["CreateConversationRequest"];
export type CreateConversationResponse = components["schemas"]["CreateConversationResponse"];
export type ConversationResponse = components["schemas"]["ConversationResponse"];
export type ChatMessageResponse = components["schemas"]["ChatMessageResponse"];
export type CitationResponse = components["schemas"]["CitationResponse"];
export type ConversationPage = components["schemas"]["ConversationPage"];
export type ChatHistoryPage = components["schemas"]["ChatHistoryPage"];
export type DeleteResponse = components["schemas"]["DeleteResponse"];
export type EmptyResponse = components["schemas"]["EmptyResponse"];
export type InterviewType = components["schemas"]["InterviewType"];
export type InterviewDifficulty = components["schemas"]["InterviewDifficulty"];
export type CreateInterviewSessionRequest = components["schemas"]["CreateInterviewSessionRequest"];
export type ResolveInterviewRoleRequest = components["schemas"]["ResolveInterviewRoleRequest"];
export type ResolveInterviewRoleResponse = components["schemas"]["ResolveInterviewRoleResponse"];
export type InterviewSessionResponse = components["schemas"]["InterviewSessionResponse"];
export type ResumeEvaluationResponse = components["schemas"]["ResumeEvaluationResponse"];
export type InterviewQuestionResponse = components["schemas"]["InterviewQuestionResponse"];
export type InterviewQuestionCitationResponse = components["schemas"]["InterviewQuestionCitationResponse"];
export type InterviewEvaluationResponse = components["schemas"]["InterviewEvaluationResponse"];
export type InterviewTurnResponse = components["schemas"]["InterviewTurnResponse"];
export type SubmitInterviewAnswerRequest = components["schemas"]["SubmitInterviewAnswerRequest"];
export type SubmitInterviewAnswerResponse = components["schemas"]["SubmitInterviewAnswerResponse"];
export type InterviewSessionPage = components["schemas"]["InterviewSessionPage"];
export type InterviewReportItemResponse = components["schemas"]["InterviewReportItemResponse"];
export type InterviewReportResponse = components["schemas"]["InterviewReportResponse"];
export type ResumeEvaluationSnapshotResponse = components["schemas"]["ResumeEvaluationSnapshotResponse"];
export type InterviewReportPage = components["schemas"]["InterviewReportPage"];
