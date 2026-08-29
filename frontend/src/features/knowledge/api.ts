import service from "@/lib/request";
import type {
  DeleteResponse,
  KnowledgeBaseCreateRequest,
  KnowledgeBaseList,
  KnowledgeBaseResponse,
  KnowledgeDocumentList,
  KnowledgeDocumentResponse,
} from "@/features/knowledge/types";

const pageParams = (current: number, size: number) => ({
  params: { current, size },
});

export const knowledgeApi = {
  listBases: (current = 1, size = 50) =>
    service.get<KnowledgeBaseList>(
      "/xunzhi/v1/knowledge-bases",
      pageParams(current, size),
    ),
  createBase: (payload: KnowledgeBaseCreateRequest) =>
    service.post<KnowledgeBaseResponse>("/xunzhi/v1/knowledge-bases", payload),
  deleteBase: (baseId: string) =>
    service.delete<DeleteResponse>(`/xunzhi/v1/knowledge-bases/${baseId}`),
  listDocuments: (baseId: string, current = 1, size = 100) =>
    service.get<KnowledgeDocumentList>(
      `/xunzhi/v1/knowledge-bases/${baseId}/documents`,
      pageParams(current, size),
    ),
  uploadDocument: (
    baseId: string,
    file: File,
    onUploadProgress?: (percent: number) => void,
  ) => {
    const formData = new FormData();
    formData.append("file", file, file.name);
    return service.post<KnowledgeDocumentResponse, FormData>(
      `/xunzhi/v1/knowledge-bases/${baseId}/documents`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (event.total) {
            onUploadProgress?.(Math.round((event.loaded / event.total) * 100));
          }
        },
      },
    );
  },
  deleteDocument: (documentId: string) =>
    service.delete<DeleteResponse>(
      `/xunzhi/v1/knowledge-documents/${documentId}`,
    ),
};
