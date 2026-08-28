import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backendRoot = path.resolve(frontendRoot, "..", "backend-python");
const python =
  process.env.PYTHON ||
  process.env.PYTHON3 ||
  (process.platform === "win32"
    ? path.join(backendRoot, ".venv312", "Scripts", "python.exe")
    : path.join(backendRoot, ".venv312", "bin", "python"));
const exportCode = [
  "import json",
  "from app.main import app",
  "print(json.dumps(app.openapi(), ensure_ascii=False))",
].join(";");

const result = spawnSync(python, ["-c", exportCode], {
  cwd: backendRoot,
  encoding: "utf8",
});

if (result.status !== 0) {
  process.stderr.write(result.stderr || "Unable to export FastAPI OpenAPI schema.\n");
  process.exit(result.status ?? 1);
}

const spec = JSON.parse(result.stdout);
const schemas = spec.components?.schemas ?? {};
const selected = [
  { exportName: "LoginRequest", schemaName: "LoginRequest" },
  {
    exportName: "MessageResponse",
    schemaName: "app__modules__auth__schemas__MessageResponse",
  },
  { exportName: "RefreshRequest", schemaName: "RefreshRequest" },
  { exportName: "RegisterRequest", schemaName: "RegisterRequest" },
  { exportName: "TokenResponse", schemaName: "TokenResponse" },
  { exportName: "UserResponse", schemaName: "UserResponse" },
  { exportName: "KnowledgeBaseCreateRequest", schemaName: "KnowledgeBaseCreateRequest" },
  { exportName: "KnowledgeBaseResponse", schemaName: "KnowledgeBaseResponse" },
  { exportName: "KnowledgeDocumentResponse", schemaName: "KnowledgeDocumentResponse" },
  { exportName: "KnowledgeBasePage", schemaName: "PageResponse_KnowledgeBaseResponse_" },
  { exportName: "KnowledgeDocumentPage", schemaName: "PageResponse_KnowledgeDocumentResponse_" },
  { exportName: "ChatRequest", schemaName: "ChatRequest" },
  { exportName: "CreateConversationRequest", schemaName: "CreateConversationRequest" },
  { exportName: "CreateConversationResponse", schemaName: "CreateConversationResponse" },
  { exportName: "ConversationResponse", schemaName: "ConversationResponse" },
  { exportName: "ChatMessageResponse", schemaName: "app__modules__chat__schemas__MessageResponse" },
  { exportName: "CitationResponse", schemaName: "CitationResponse" },
  { exportName: "ConversationPage", schemaName: "PageResponse_ConversationResponse_" },
  { exportName: "ChatHistoryPage", schemaName: "PageResponse_MessageResponse_" },
  { exportName: "DeleteResponse", schemaName: "DeleteResponse" },
  { exportName: "EmptyResponse", schemaName: "EmptyResponse" },
  { exportName: "InterviewType", schemaName: "InterviewType" },
  { exportName: "InterviewDifficulty", schemaName: "InterviewDifficulty" },
  {
    exportName: "CreateInterviewSessionRequest",
    schemaName: "CreateInterviewSessionRequest",
  },
  {
    exportName: "InterviewSessionResponse",
    schemaName: "InterviewSessionResponse",
  },
  {
    exportName: "InterviewQuestionResponse",
    schemaName: "InterviewQuestionResponse",
  },
  {
    exportName: "InterviewQuestionCitationResponse",
    schemaName: "InterviewQuestionCitationResponse",
  },
  {
    exportName: "InterviewEvaluationResponse",
    schemaName: "InterviewEvaluationResponse",
  },
  { exportName: "InterviewTurnResponse", schemaName: "InterviewTurnResponse" },
  {
    exportName: "SubmitInterviewAnswerRequest",
    schemaName: "SubmitInterviewAnswerRequest",
  },
  {
    exportName: "SubmitInterviewAnswerResponse",
    schemaName: "SubmitInterviewAnswerResponse",
  },
  {
    exportName: "InterviewSessionPage",
    schemaName: "InterviewPageResponse_InterviewSessionResponse_",
  },
  {
    exportName: "InterviewReportItemResponse",
    schemaName: "InterviewReportItemResponse",
  },
  {
    exportName: "InterviewReportResponse",
    schemaName: "InterviewReportResponse",
  },
  {
    exportName: "InterviewReportPage",
    schemaName: "InterviewReportPageResponse_InterviewReportResponse_",
  },
];

const exportNameBySchema = new Map(selected.map((entry) => [entry.schemaName, entry.exportName]));
const refName = (ref) => {
  const schemaName = ref.split("/").at(-1);
  const exportName = exportNameBySchema.get(schemaName) ?? schemaName;
  return `components["schemas"]["${exportName}"]`;
};
const schemaType = (schema) => {
  if (!schema) return "unknown";
  if (schema.$ref) return refName(schema.$ref);
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(" | ");
  if (schema.anyOf || schema.oneOf) {
    return (schema.anyOf ?? schema.oneOf).map(schemaType).join(" | ");
  }
  if (schema.type === "array") return `Array<${schemaType(schema.items)}>`;
  if (schema.type === "null") return "null";
  if (schema.type === "object" || schema.properties) {
    const required = new Set(schema.required ?? []);
    const properties = Object.entries(schema.properties ?? {}).map(
      ([name, value]) => `      ${JSON.stringify(name)}${required.has(name) ? "" : "?"}: ${schemaType(value)};`,
    );
    return properties.length ? `{\n${properties.join("\n")}\n    }` : "Record<string, unknown>";
  }
  if (schema.type === "string") return "string";
  if (schema.type === "integer" || schema.type === "number") return "number";
  if (schema.type === "boolean") return "boolean";
  return "unknown";
};

const declarations = selected
  .filter((entry) => schemas[entry.schemaName])
  .map((entry) => `    ${entry.exportName}: ${schemaType(schemas[entry.schemaName])};`)
  .join("\n");
const generatedNames = selected.filter((entry) => schemas[entry.schemaName]);
const output = `// AUTO-GENERATED from backend FastAPI OpenAPI. Do not edit manually.\n\nexport interface components {\n  schemas: {\n${declarations}\n  };\n}\n\n${generatedNames.map((entry) => `export type ${entry.exportName} = components["schemas"]["${entry.exportName}"];`).join("\n")}\n`;

await mkdir(path.join(frontendRoot, "src", "api"), { recursive: true });
await writeFile(path.join(frontendRoot, "src", "api", "generated.ts"), output, "utf8");
console.log(`Generated ${generatedNames.length} OpenAPI schema types.`);
