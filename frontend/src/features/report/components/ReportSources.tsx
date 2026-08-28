import { sourcePage, sourceText } from "@/features/report/types";

export function ReportSources({ sources }: { sources: Array<Record<string, unknown>> }) {
  if (!sources.length) return <p className="report-empty-copy">本轮没有引用来源。</p>;
  return (
    <ul className="report-source-list">
      {sources.map((source, index) => {
        const sourceId = sourceText(source, "sourceId") ?? `S${index + 1}`;
        const fileName = sourceText(source, "fileName") ?? sourceText(source, "documentName") ?? "未命名文档";
        const page = sourcePage(source);
        const summary = sourceText(source, "summary") ?? sourceText(source, "excerpt");
        return (
          <li key={`${sourceId}-${fileName}-${index}`}>
            <details>
              <summary><span className="source-id">{sourceId}</span> {fileName}{page ? ` · 第 ${page} 页` : ""}</summary>
              {summary ? <p>{summary}</p> : null}
            </details>
          </li>
        );
      })}
    </ul>
  );
}
