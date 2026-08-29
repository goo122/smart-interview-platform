import { useEffect, useRef, useState } from "react";
import { Check, FileText, Loader2, Plus, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  formatFileSize,
  hasReadyDocument,
  type KnowledgeDocument,
} from "@/features/knowledge/types";
import {
  useKnowledgeBaseReadiness,
  useKnowledgeDocuments,
  useKnowledgeMutations,
} from "@/features/knowledge/hooks";

const MAX_FILE_SIZE = 20 * 1024 * 1024;
const statusLabels: Record<string, string> = {
  PENDING: "等待处理",
  PROCESSING: "处理中",
  READY: "已就绪",
  FAILED: "处理失败",
};

type KnowledgePanelProps = {
  selectedBaseId: string | null;
  onSelect: (baseId: string | null) => void;
  variant?: "default" | "sidebar";
};

export function KnowledgePanel({
  selectedBaseId,
  onSelect,
  variant = "default",
}: KnowledgePanelProps) {
  const isSidebar = variant === "sidebar";
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [managedBaseId, setManagedBaseId] = useState<string | null>(selectedBaseId);
  const [progress, setProgress] = useState<number | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const basesQuery = useKnowledgeBaseReadiness();
  const effectiveBaseId = selectedBaseId ?? managedBaseId;
  const documentsQuery = useKnowledgeDocuments(effectiveBaseId);
  const { create, remove, upload, removeDocument } = useKnowledgeMutations();
  const bases = basesQuery.data?.records ?? [];

  useEffect(() => {
    const documents = documentsQuery.data?.records ?? [];
    if (effectiveBaseId && hasReadyDocument(documents)) {
      onSelect(effectiveBaseId);
    }
  }, [documentsQuery.data?.records, effectiveBaseId, onSelect]);

  useEffect(() => {
    if (selectedBaseId || managedBaseId || basesQuery.readyBaseIds.size === 0) {
      return;
    }
    const firstReadyBaseId = [...basesQuery.readyBaseIds][0];
    if (!firstReadyBaseId) {
      return;
    }
    setManagedBaseId(firstReadyBaseId);
    onSelect(firstReadyBaseId);
  }, [
    basesQuery.readyBaseIds,
    managedBaseId,
    onSelect,
    selectedBaseId,
  ]);

  const submitCreate = async () => {
    const cleanName = name.trim();
    if (!cleanName || create.isPending) return;
    try {
      const created = await create.mutateAsync({
        name: cleanName,
        description: description.trim() || null,
      });
      setName("");
      setDescription("");
      setManagedBaseId(created.id);
      onSelect(null);
    } catch {
      // The mutation error is rendered below without exposing internals.
    }
  };

  const handleFile = async (file: File | undefined) => {
    if (!file || !effectiveBaseId || upload.isPending) return;
    if (file.type !== "application/pdf" || !file.name.toLowerCase().endsWith(".pdf")) {
      setFileError("只能上传 PDF 文件");
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setFileError(`文件不能超过 ${formatFileSize(MAX_FILE_SIZE)}`);
      return;
    }
    setFileError(null);
    setProgress(0);
    try {
      await upload.mutateAsync({
        baseId: effectiveBaseId,
        file,
        onProgress: setProgress,
      });
      setProgress(100);
    } catch {
      // The mutation error is rendered below without exposing internals.
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const selectBase = (baseId: string) => {
    setManagedBaseId(baseId);
    const index = bases.findIndex((base) => base.id === baseId);
    const documents = basesQuery.documentQueries[index]?.data?.records ?? [];
    onSelect(hasReadyDocument(documents) ? baseId : null);
  };

  return (
    <section
      aria-label="知识库管理"
      className={cn(
        "flex h-full flex-col rounded-2xl border border-slate-200 bg-slate-50/70 p-4 shadow-sm",
        isSidebar ? "min-h-0 overflow-y-auto" : "",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            KNOWLEDGE
          </p>
          <h2 className="mt-1 text-sm font-semibold text-slate-900">简历知识库</h2>
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-500">
          {bases.length} 个
        </span>
      </div>
      {selectedBaseId ? (
        <p className="mt-2 text-xs font-medium text-emerald-700">RAG 知识库模式</p>
      ) : null}

      <div
        className={cn(
          "mt-3 grid gap-2",
          isSidebar ? "grid-cols-1" : "sm:grid-cols-[1fr_1fr_auto]",
        )}
      >
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="新知识库名称"
          maxLength={200}
          className="h-9 bg-white"
        />
        <Input
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="描述（可选）"
          maxLength={500}
          className="h-9 bg-white"
        />
        <Button
          type="button"
          onClick={() => void submitCreate()}
          disabled={!name.trim() || create.isPending}
          className={cn("h-9 rounded-full", isSidebar && "w-full")}
        >
          {create.isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Plus className="mr-1 h-4 w-4" />}
          创建知识库
        </Button>
      </div>

      {create.isError ? <p className="mt-2 text-xs text-red-600">知识库创建失败，请稍后重试。</p> : null}
      {basesQuery.isError ? <p className="mt-2 text-xs text-red-600">知识库加载失败，请刷新重试。</p> : null}

      <div className={cn("mt-3 flex gap-2", isSidebar ? "flex-col" : "flex-wrap")}>
        {bases.map((base, index) => {
          const documents = basesQuery.documentQueries[index]?.data?.records ?? [];
          const ready = hasReadyDocument(documents);
          const selected = base.id === effectiveBaseId;
          return (
            <div
              key={base.id}
              className={cn("flex items-center gap-1", isSidebar && "w-full")}
            >
              <Button
                type="button"
                variant={selected ? "secondary" : "outline"}
                className={cn(
                  "h-8 rounded-full bg-white text-xs",
                  isSidebar && "min-w-0 flex-1 justify-start",
                  selected && "border-slate-400",
                )}
                onClick={() => selectBase(base.id)}
              >
                {ready ? <Check className="mr-1 h-3.5 w-3.5 text-emerald-600" /> : <FileText className="mr-1 h-3.5 w-3.5 text-slate-400" />}
                {base.name}
                <span className="ml-1 text-[10px] text-slate-400">{ready ? "已就绪" : "待上传"}</span>
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7 rounded-full text-slate-400 hover:text-red-600"
                aria-label={`删除知识库 ${base.name}`}
                onClick={() => {
                  if (window.confirm(`确定删除知识库“${base.name}”及其文档吗？`)) {
                    remove.mutate(base.id, {
                      onSuccess: () => {
                        if (managedBaseId === base.id) setManagedBaseId(null);
                        if (selectedBaseId === base.id) onSelect(null);
                      },
                    });
                  }
                }}
                disabled={remove.isPending}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          );
        })}
        {!basesQuery.isPending && bases.length === 0 ? <p className="text-xs text-slate-400">还没有知识库，创建一个开始吧。</p> : null}
      </div>

      {effectiveBaseId ? (
        <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-slate-700">上传简历 PDF</p>
              <p className="mt-0.5 text-[11px] text-slate-400">仅支持 PDF，大小不超过 {formatFileSize(MAX_FILE_SIZE)}</p>
            </div>
            <label className="upload-button inline-flex cursor-pointer items-center rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
              <Upload className="mr-1 h-3.5 w-3.5" />
              上传 PDF
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(event) => void handleFile(event.target.files?.[0])}
                disabled={upload.isPending}
              />
            </label>
          </div>
          {upload.isPending && progress !== null ? <progress className="mt-2 h-1.5 w-full" value={progress} max={100} aria-label="上传进度" /> : null}
          {fileError ? <p className="mt-2 text-xs text-red-600">{fileError}</p> : null}
          {upload.isError ? <p className="mt-2 text-xs text-red-600">文档上传失败，请稍后重试。</p> : null}
          <div className="mt-2 space-y-1.5">
            {(documentsQuery.data?.records ?? []).map((document) => (
              <DocumentRow key={document.id} document={document} onDelete={() => removeDocument.mutate(document.id)} />
            ))}
            {documentsQuery.isPending ? <p className="text-xs text-slate-400">正在加载文档…</p> : null}
            {!documentsQuery.isPending && !(documentsQuery.data?.records.length ?? 0) ? <p className="text-xs text-slate-400">上传 PDF 后会在这里显示处理状态。</p> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function DocumentRow({ document, onDelete }: { document: KnowledgeDocument; onDelete: () => void }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/80 px-2.5 py-2">
      <FileText className="h-4 w-4 shrink-0 text-slate-500" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-slate-700" title={document.original_filename}>{document.original_filename}</p>
        <p className="text-[11px] text-slate-400">{formatFileSize(document.size_bytes)} · {statusLabels[document.status] ?? document.status}</p>
        {document.status === "FAILED" && document.error_message ? <p className="text-[11px] text-red-600">{document.error_message}</p> : null}
      </div>
      <Button type="button" variant="ghost" size="icon" className="h-7 w-7 text-slate-400 hover:text-red-600" aria-label={`删除文档 ${document.original_filename}`} onClick={onDelete}>
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
