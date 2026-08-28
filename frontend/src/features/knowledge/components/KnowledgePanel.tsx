import { useRef, useState } from "react";
import { toUserMessage } from "@/api/errors";
import { frontendEnv } from "@/config/env";
import { useKnowledgeBaseReadiness, useKnowledgeDocuments, useKnowledgeMutations } from "@/features/knowledge/hooks";
import { formatFileSize, hasReadyDocument, type KnowledgeDocument } from "@/features/knowledge/types";

type KnowledgePanelProps = {
  selectedBaseId: string | null;
  onSelect: (baseId: string | null) => void;
};

const statusLabels: Record<string, string> = {
  PENDING: "等待处理",
  PROCESSING: "处理中",
  READY: "已就绪",
  FAILED: "处理失败",
};

export function KnowledgePanel({ selectedBaseId, onSelect }: KnowledgePanelProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [managedBaseId, setManagedBaseId] = useState<string | null>(selectedBaseId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const effectiveManagedBaseId = selectedBaseId ?? managedBaseId;
  const basesQuery = useKnowledgeBaseReadiness();
  const documentsQuery = useKnowledgeDocuments(effectiveManagedBaseId);
  const { create, remove, upload, removeDocument } = useKnowledgeMutations();
  const bases = basesQuery.data?.records ?? [];
  const selectedBase = bases.find((base) => base.id === effectiveManagedBaseId);

  const submitCreate = async () => {
    const cleanName = name.trim();
    if (!cleanName || create.isPending) return;
    try {
      await create.mutateAsync({ name: cleanName, description: description.trim() || null });
      setName("");
      setDescription("");
      // A newly created base has no READY document yet, so it cannot be selected for RAG.
      onSelect(null);
    } catch {
      // Mutation state below contains the user-safe error.
    }
  };

  const handleFile = async (file: File | undefined) => {
    if (!file || !effectiveManagedBaseId || upload.isPending) return;
    const clearInput = () => { if (fileInputRef.current) fileInputRef.current.value = ""; };
    if (file.type !== "application/pdf" || !file.name.toLowerCase().endsWith(".pdf")) {
      setFileError("只能上传 PDF 文件");
      clearInput();
      return;
    }
    if (file.size > frontendEnv.knowledgeMaxFileSizeBytes) {
      setFileError(`文件不能超过 ${formatFileSize(frontendEnv.knowledgeMaxFileSizeBytes)}`);
      clearInput();
      return;
    }
    setFileError(null);
    setProgress(0);
    try {
      await upload.mutateAsync({ baseId: effectiveManagedBaseId, file, onProgress: setProgress });
      setProgress(100);
    } catch {
      // Mutation state below contains the user-safe error.
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const selectBase = (baseId: string) => {
    setManagedBaseId(baseId);
    const documents = basesQuery.documentQueries[bases.findIndex((base) => base.id === baseId)]?.data?.records ?? [];
    if (hasReadyDocument(documents)) onSelect(baseId);
  };

  return (
    <aside className="knowledge-panel" aria-label="知识库管理">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">KNOWLEDGE</p>
          <h2>知识库</h2>
        </div>
        <span className="panel-count">{bases.length}</span>
      </div>
      {basesQuery.isPending ? <p className="panel-muted">正在加载知识库…</p> : null}
      {basesQuery.isError ? (
        <div className="panel-error" role="alert">
          <span>{toUserMessage(basesQuery.error)}</span>
          <button type="button" onClick={() => basesQuery.refetch()}>重试</button>
        </div>
      ) : null}
      <div className="knowledge-list">
        {bases.map((base) => {
          const index = bases.findIndex((item) => item.id === base.id);
          const documents = basesQuery.documentQueries[index]?.data?.records ?? [];
          const ready = hasReadyDocument(documents);
          return (
            <div className={`knowledge-item ${base.id === effectiveManagedBaseId ? "selected" : ""}`} key={base.id}>
              <button type="button" className="knowledge-item-main" onClick={() => selectBase(base.id)}>
                <span className="knowledge-icon">⌁</span>
                <span className="knowledge-item-copy">
                  <strong>{base.name}</strong>
                  <small>{ready ? `${documents.filter((doc) => doc.status === "READY").length} 个可用文档` : "暂无可用文档"}</small>
                </span>
                <span className={`ready-dot ${ready ? "on" : ""}`} />
              </button>
              <button
                type="button"
                className="icon-button"
                aria-label={`删除知识库 ${base.name}`}
                onClick={() => {
                  if (window.confirm(`确定删除知识库“${base.name}”及其文档吗？`)) {
                    remove.mutate(base.id, { onSuccess: () => { if (selectedBaseId === base.id) onSelect(null); if (managedBaseId === base.id) setManagedBaseId(null); } });
                  }
                }}
                disabled={remove.isPending}
              >
                ×
              </button>
            </div>
          );
        })}
        {!basesQuery.isPending && !bases.length ? <p className="panel-muted">还没有知识库，创建一个开始吧。</p> : null}
      </div>

      <div className="knowledge-create">
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="新知识库名称" maxLength={200} />
        <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="描述（可选）" maxLength={500} />
        <button type="button" className="button button-secondary button-full" onClick={submitCreate} disabled={!name.trim() || create.isPending}>
          {create.isPending ? "创建中…" : "+ 创建知识库"}
        </button>
      </div>
      {create.isError ? <p className="panel-error" role="alert">{toUserMessage(create.error)}</p> : null}

      {selectedBase ? (
        <div className="document-section">
          <div className="document-heading">
            <div>
              <strong>{selectedBase.name}</strong>
              <small>文档处理状态</small>
            </div>
            <label className="upload-button">
              上传 PDF
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => void handleFile(event.target.files?.[0])}
                disabled={upload.isPending}
              />
            </label>
          </div>
          {progress !== null && upload.isPending ? <progress value={progress} max={100} aria-label="上传进度" /> : null}
          {fileError ? <p className="panel-error" role="alert">{fileError}</p> : null}
          {upload.isError ? <p className="panel-error" role="alert">{toUserMessage(upload.error)}</p> : null}
          {documentsQuery.isPending ? <p className="panel-muted">正在加载文档…</p> : null}
          {documentsQuery.isError ? <p className="panel-error" role="alert">{toUserMessage(documentsQuery.error)}</p> : null}
          <div className="document-list">
            {(documentsQuery.data?.records ?? []).map((document) => (
              <DocumentRow key={document.id} document={document} onDelete={() => removeDocument.mutate(document.id)} />
            ))}
            {!documentsQuery.isPending && !(documentsQuery.data?.records.length ?? 0) ? <p className="panel-muted">上传 PDF 后会在这里显示处理状态。</p> : null}
          </div>
        </div>
      ) : null}
      <small className="panel-footnote">仅支持 PDF，大小不超过 {formatFileSize(frontendEnv.knowledgeMaxFileSizeBytes)}。</small>
    </aside>
  );
}

function DocumentRow({ document, onDelete }: { document: KnowledgeDocument; onDelete: () => void }) {
  return (
    <div className="document-row">
      <span className="document-file-icon">PDF</span>
      <span className="document-copy">
        <strong title={document.original_filename}>{document.original_filename}</strong>
        <small>{formatFileSize(document.size_bytes)} · {statusLabels[document.status] ?? document.status}</small>
        {document.status === "FAILED" && document.error_message ? <small className="document-error">{document.error_message}</small> : null}
      </span>
      <button type="button" className="icon-button" aria-label={`删除文档 ${document.original_filename}`} onClick={() => { if (window.confirm("确定删除该文档吗？")) onDelete(); }}>×</button>
    </div>
  );
}
