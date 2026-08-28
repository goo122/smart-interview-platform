import { Suspense, lazy, useEffect, useRef, useState } from "react";

const InterviewResumePdfDocument = lazy(
  () => import("@/components/interview/InterviewResumePdfDocument"),
);

type InterviewResumePreviewContentProps = {
  resumePreviewSource: File | string | undefined;
  resumePreviewError: string | null;
  resumeOpenPreviewUrl: string | null;
  numPages: number;
  maxPages?: number;
  onLoadSuccess: (numPages: number) => void;
  onLoadError: (message: string) => void;
};

export default function InterviewResumePreviewContent({
  resumePreviewSource,
  resumePreviewError,
  resumeOpenPreviewUrl,
  numPages,
  maxPages,
  onLoadSuccess,
  onLoadError,
}: InterviewResumePreviewContentProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [pageWidth, setPageWidth] = useState(760);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const nextWidth = Math.max(320, Math.floor(entry.contentRect.width) - 24);
      setPageWidth((previous) =>
        previous === nextWidth ? previous : nextWidth,
      );
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const visiblePages = Math.max(
    1,
    Math.min(numPages, typeof maxPages === "number" ? maxPages : numPages),
  );

  return (
    <div
      ref={containerRef}
      className="h-full overflow-x-hidden overflow-y-scroll overscroll-contain rounded-xl border border-slate-100 bg-white p-3 [scrollbar-gutter:stable]"
      onWheelCapture={(event) => event.stopPropagation()}
    >
      {resumePreviewSource ? (
        <Suspense
          fallback={
            <div className="flex min-h-[420px] items-center justify-center p-6 text-sm text-slate-500">
              PDF 预览加载中...
            </div>
          }
        >
          <InterviewResumePdfDocument
            resumePreviewSource={resumePreviewSource}
            resumeOpenPreviewUrl={resumeOpenPreviewUrl}
            visiblePages={visiblePages}
            pageWidth={pageWidth}
            onLoadSuccess={onLoadSuccess}
            onLoadError={onLoadError}
          />
        </Suspense>
      ) : resumePreviewError ? (
        <div className="space-y-2 p-6 text-sm text-amber-600">
          <div>简历预览加载失败：{resumePreviewError}</div>
          {resumeOpenPreviewUrl ? (
            <a
              href={resumeOpenPreviewUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex text-sky-600 underline underline-offset-4"
            >
              在新窗口打开
            </a>
          ) : null}
        </div>
      ) : (
        <div className="flex min-h-[420px] items-center justify-center p-6 text-sm text-slate-500">
          请先上传 PDF 简历
        </div>
      )}
    </div>
  );
}
