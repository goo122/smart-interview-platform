import { describe, expect, it } from "vitest";
import { formatFileSize, hasReadyDocument, isDocumentProcessing } from "@/features/knowledge/types";

const document = (status: string) => ({ status }) as never;

describe("knowledge document status helpers", () => {
  it("polls only pending and processing documents", () => {
    expect(isDocumentProcessing(document("PENDING"))).toBe(true);
    expect(isDocumentProcessing(document("PROCESSING"))).toBe(true);
    expect(isDocumentProcessing(document("READY"))).toBe(false);
    expect(isDocumentProcessing(document("FAILED"))).toBe(false);
  });

  it("allows RAG only when a base has a ready document", () => {
    expect(hasReadyDocument([document("PROCESSING")])).toBe(false);
    expect(hasReadyDocument([document("FAILED"), document("READY")])).toBe(true);
  });

  it("formats upload sizes for the UI", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(2 * 1024 * 1024)).toBe("2.0 MB");
  });
});
