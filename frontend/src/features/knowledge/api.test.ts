import type { AxiosAdapter, AxiosResponse } from "axios";
import { afterEach, describe, expect, it } from "vitest";
import { resetApiClientForTests, setApiAdapterForTests } from "@/api/client";
import { knowledgeApi } from "@/features/knowledge/api";
import { tokenStore } from "@/lib/tokenStore";

const response = <T>(config: Parameters<AxiosAdapter>[0], data: T): AxiosResponse<T> => ({
  data,
  status: 200,
  statusText: "OK",
  headers: {},
  config,
});

afterEach(() => {
  tokenStore.clear();
  resetApiClientForTests();
});

describe("knowledge API", () => {
  it("uses the paginated knowledge-base contract", async () => {
    tokenStore.setTokens("access", "refresh");
    let seen: { url?: string; method?: string; params?: unknown; authorization?: unknown } = {};
    setApiAdapterForTests(async (config) => {
      seen = { url: config.url, method: config.method, params: config.params, authorization: config.headers.Authorization };
      return response(config, { records: [], total: 0, size: 50, current: 1, pages: 0 });
    });

    await knowledgeApi.listBases();
    expect(seen).toMatchObject({
      url: "/xunzhi/v1/knowledge-bases",
      method: "get",
      params: { current: 1, size: 50 },
      authorization: "Bearer access",
    });
  });

  it("sends PDF uploads as multipart form data and reports progress", async () => {
    let body: unknown;
    let contentType: unknown;
    setApiAdapterForTests(async (config) => {
      body = config.data;
      contentType = config.headers["Content-Type"];
      return response(config, {
        id: "doc-1",
        knowledge_base_id: "base-1",
        original_filename: "resume.pdf",
        safe_filename: "safe.pdf",
        content_type: "application/pdf",
        size_bytes: 4,
        sha256: "hash",
        status: "PENDING",
        page_count: 0,
        chunk_count: 0,
        error_code: null,
        error_message: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        completed_at: null,
      });
    });
    const file = new File([new Uint8Array([37, 80, 68, 70])], "resume.pdf", { type: "application/pdf" });
    await knowledgeApi.uploadDocument("base-1", file);
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("file")).toBeInstanceOf(File);
    expect(contentType).toBe("multipart/form-data");
  });
});
