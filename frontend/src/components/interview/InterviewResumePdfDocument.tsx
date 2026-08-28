import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

type InterviewResumePdfDocumentProps = {
  resumePreviewSource: File | string;
  resumeOpenPreviewUrl: string | null;
  visiblePages: number;
  pageWidth: number;
  onLoadSuccess: (numPages: number) => void;
  onLoadError: (message: string) => void;
};

export default function InterviewResumePdfDocument({
  resumePreviewSource,
  resumeOpenPreviewUrl,
  visiblePages,
  pageWidth,
  onLoadSuccess,
  onLoadError,
}: InterviewResumePdfDocumentProps) {
  return (
    <Document
      file={resumePreviewSource}
      loading={
        <div className="flex min-h-[420px] items-center justify-center p-6 text-sm text-slate-500">
          简历加载中...
        </div>
      }
      noData={
        <div className="flex min-h-[420px] items-center justify-center p-6 text-sm text-slate-500">
          暂无可预览的简历文件
        </div>
      }
      error={
        <div className="space-y-2 p-6 text-sm text-amber-600">
          <div>PDF 预览失败。</div>
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
      }
      onLoadSuccess={(info) => {
        onLoadSuccess(info.numPages);
      }}
      onLoadError={(error) => {
        const message =
          error instanceof Error ? error.message : "Resume preview failed";
        onLoadError(message);
      }}
      onSourceError={(error) => {
        const message =
          error instanceof Error ? error.message : "Resume file load failed";
        onLoadError(message);
      }}
    >
      <div className="space-y-4">
        {Array.from({ length: visiblePages }, (_, index) => (
          <div key={`page_${index + 1}`} className="flex justify-center">
            <Page
              pageNumber={index + 1}
              width={pageWidth}
              renderAnnotationLayer={false}
              renderTextLayer={false}
            />
          </div>
        ))}
      </div>
    </Document>
  );
}
