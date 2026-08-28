import type { KnowledgeBaseResponse, KnowledgeDocumentResponse } from "@/api/generated";

export type DocumentStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

export type KnowledgeBase = KnowledgeBaseResponse;
export type KnowledgeDocument = KnowledgeDocumentResponse;

export const isDocumentProcessing = (document: KnowledgeDocument) =>
  document.status === "PENDING" || document.status === "PROCESSING";

export const hasReadyDocument = (documents: KnowledgeDocument[]) =>
  documents.some((document) => document.status === "READY");

export const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};
