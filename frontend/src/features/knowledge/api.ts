import { apiClient, requestData } from "@/api/client";
import type {
  DeleteResponse,
  KnowledgeBaseCreateRequest,
  KnowledgeBasePage,
  KnowledgeBaseResponse,
  KnowledgeDocumentPage,
  KnowledgeDocumentResponse,
} from "@/api/generated";

const pageParams = (current: number, size: number) => ({ params: { current, size } });

export const knowledgeApi = {
  listBases: (current = 1, size = 50) =>
    requestData(apiClient.get<KnowledgeBasePage>("/xunzhi/v1/knowledge-bases", pageParams(current, size))),
  createBase: (payload: KnowledgeBaseCreateRequest) =>
    requestData(apiClient.post<KnowledgeBaseResponse>("/xunzhi/v1/knowledge-bases", payload)),
  deleteBase: (baseId: string) =>
    requestData(apiClient.delete<DeleteResponse>(`/xunzhi/v1/knowledge-bases/${baseId}`)),
  listDocuments: (baseId: string, current = 1, size = 100) =>
    requestData(
      apiClient.get<KnowledgeDocumentPage>(
        `/xunzhi/v1/knowledge-bases/${baseId}/documents`,
        pageParams(current, size),
      ),
    ),
  uploadDocument: (
    baseId: string,
    file: File,
    onUploadProgress?: (percent: number) => void,
  ) => {
    const formData = new FormData();
    formData.append("file", file, file.name);
    return requestData(
      apiClient.post<KnowledgeDocumentResponse>(
        `/xunzhi/v1/knowledge-bases/${baseId}/documents`,
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
          onUploadProgress: (event) => {
            if (event.total) onUploadProgress?.(Math.round((event.loaded / event.total) * 100));
          },
        },
      ),
    );
  },
  deleteDocument: (documentId: string) =>
    requestData(apiClient.delete<DeleteResponse>(`/xunzhi/v1/knowledge-documents/${documentId}`)),
};
