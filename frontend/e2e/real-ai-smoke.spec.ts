import { expect, test } from "@playwright/test";

const enabled = process.env.RUN_REAL_AI_SMOKE === "1";

const createSyntheticPdf = () => {
  const content = "BT /F1 12 Tf 72 720 Td (Synthetic backend engineer resume.) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(pdf, "ascii"));
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xrefOffset = Buffer.byteLength(pdf, "ascii");
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  offsets.slice(1).forEach((offset) => {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  });
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  return Buffer.from(pdf, "ascii");
};

type JsonRecord = Record<string, unknown>;

test.describe("real provider smoke", () => {
  test.skip(
    !enabled,
    "Set RUN_REAL_AI_SMOKE=1 to explicitly authorize the real-provider smoke test.",
  );

  test("runs the explicitly enabled DashScope provider smoke flow", async ({ page }) => {
  test.setTimeout(360_000);
  const unique = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  const username = `real_smoke_${unique}`;
  const email = `${username}@example.test`;
  const baseUrl = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:28080";
  const apiUrl = (path: string) => new URL(path, baseUrl).toString();
  // The API performs one document and one query probe during startup dimension validation.
  const safeCounters = { chatInvocations: 0, embeddingOperations: 2 };

  const register = await page.request.post(apiUrl("/api/v1/auth/register"), {
    data: { username, email, password: "smoke-password-123" },
  });
  expect(register.status()).toBe(201);
  const login = await page.request.post(apiUrl("/api/v1/auth/login"), {
    data: { account: email, password: "smoke-password-123" },
  });
  expect(login.ok()).toBeTruthy();
  const tokenResponse = (await login.json()) as { access_token: string };
  const headers = { Authorization: `Bearer ${tokenResponse.access_token}` };

  const json = async <T = JsonRecord>(path: string): Promise<T> => {
    const response = await page.request.get(apiUrl(path), { headers });
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as T;
  };
  const postJson = async <T = JsonRecord>(
    path: string,
    data?: Record<string, unknown>,
  ): Promise<T> => {
    const response = await page.request.post(apiUrl(path), { headers, data });
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as T;
  };

  const models = await json<{ records: JsonRecord[] }>(
    "/api/xunzhi/v1/ai-properties?isEnabled=1&size=100",
  );
  expect(models.records).toHaveLength(1);
  const model = models.records[0];
  expect(model?.aiType).toBe("openai_compatible");
  expect(model?.modelName).toBeTruthy();
  expect(JSON.stringify(models).toLowerCase()).not.toMatch(
    /apikey|apisecret|authorization|systemprompt/,
  );

  const bases = await json<{ records: JsonRecord[] }>(
    "/api/xunzhi/v1/knowledge-bases?current=1&size=20",
  );
  expect(bases.records).toBeDefined();
  const base = await postJson<{ id: string }>("/api/xunzhi/v1/knowledge-bases", {
    name: `Real smoke ${unique}`,
  });
  const baseId = base.id;
  const upload = await page.request.post(
    apiUrl(`/api/xunzhi/v1/knowledge-bases/${baseId}/documents`),
    {
      headers,
      multipart: {
        file: {
          name: "synthetic-resume.pdf",
          mimeType: "application/pdf",
          buffer: createSyntheticPdf(),
        },
      },
    },
  );
  expect(upload.status()).toBe(201);
  const documentId = ((await upload.json()) as { id: string }).id;
  await expect
    .poll(
      async () =>
        (await json<{ status: string }>(
          `/api/xunzhi/v1/knowledge-documents/${documentId}`,
        )).status,
      { timeout: 120_000, intervals: [1_000, 2_000, 5_000] },
    )
    .toBe("READY");
  const document = await json<{ chunk_count?: number }>(
    `/api/xunzhi/v1/knowledge-documents/${documentId}`,
  );
  expect(document.chunk_count ?? 0).toBeGreaterThan(0);
  safeCounters.embeddingOperations += 1;

  const chat = await postJson<{ sessionId: string }>("/api/xunzhi/v1/ai/conversations", {
    title: `Real smoke chat ${unique}`,
    modelName: model?.modelName,
    aiId: model?.id,
  });
  const chatResponse = await page.request.post(
    apiUrl(`/api/xunzhi/v1/ai/sessions/${chat.sessionId}/chat`),
    {
      headers: { ...headers, "Content-Type": "application/json" },
      data: {
        inputMessage: "请从合成简历中指出一个技能。",
        requestId: `chat-${unique}`,
        knowledgeBaseId: baseId,
      },
    },
  );
  expect(chatResponse.ok()).toBeTruthy();
  const chatBody = (await chatResponse.body()).toString("utf8");
  expect(chatBody).toContain("event: complete");
  expect(chatBody).not.toContain("这是开发环境的模拟回答");
  safeCounters.chatInvocations += 1;
  safeCounters.embeddingOperations += 1;

  const session = await postJson<{ sessionId: string }>(
    "/api/xunzhi/v1/interview/sessions",
    {
      knowledgeBaseId: baseId,
      jobTitle: "后端工程师",
      jobDescription: "负责服务端开发、稳定性和性能优化。",
      interviewType: "TECHNICAL",
      difficulty: "MEDIUM",
      questionCount: 3,
      requestId: `session-${unique}`,
    },
  );
  const sessionId = session.sessionId;
  await expect
    .poll(
      async () =>
        (await json<{ status: string }>(
          `/api/xunzhi/v1/interview/sessions/${sessionId}`,
        )).status,
      { timeout: 180_000, intervals: [1_000, 2_000, 5_000] },
    )
    .toBe("READY");
  const prepared = await json<JsonRecord>(`/api/xunzhi/v1/interview/sessions/${sessionId}`);
  expect(prepared.resumeEvaluationStatus).toBe("COMPLETED");
  expect(prepared.resumeScore).toBeGreaterThanOrEqual(0);
  expect(prepared.resumeScore).toBeLessThanOrEqual(100);
  safeCounters.chatInvocations += 2;

  const preview = await page.request.get(
    apiUrl(`/api/xunzhi/v1/interview/sessions/${sessionId}/resume/preview`),
    { headers },
  );
  expect(preview.ok()).toBeTruthy();
  expect(preview.headers()["content-type"]).toContain("application/pdf");
  expect((await preview.body()).subarray(0, 5).toString("ascii")).toBe("%PDF-");

  const questions = await json<JsonRecord[]>(
    `/api/xunzhi/v1/interview/sessions/${sessionId}/questions`,
  );
  // The API deliberately exposes only the first question before the interview
  // starts; subsequent primary questions are revealed through current-turn.
  expect(questions).toHaveLength(1);
  expect(prepared.questionCount).toBe(3);
  expect((questions[0]?.citations as unknown[] | undefined)?.length ?? 0).toBeGreaterThan(0);
  await postJson(`/api/xunzhi/v1/interview/sessions/${sessionId}/start`);
  for (let index = 0; index < 3; index += 1) {
    const turn = await json<JsonRecord>(
      `/api/xunzhi/v1/interview/sessions/${sessionId}/current-turn`,
    );
    expect(turn.turnType).toBe("PRIMARY");
    const answerPayload = {
      turnId: turn.turnId,
      answer: "我会先拆分问题，明确边界，再通过测试和指标验证方案。",
      requestId: `answer-${unique}-${index}`,
    };
    await postJson(`/api/xunzhi/v1/interview/sessions/${sessionId}/answers`, answerPayload);
    await expect
      .poll(
        async () =>
          (await json<JsonRecord>(
            `/api/xunzhi/v1/interview/sessions/${sessionId}/turns/${turn.turnId}`,
          )).status,
        { timeout: 120_000, intervals: [1_000, 2_000, 5_000] },
      )
      .toBe("COMPLETED");
    const evaluated = await json<JsonRecord>(
      `/api/xunzhi/v1/interview/sessions/${sessionId}/turns/${turn.turnId}`,
    );
    const evaluation = evaluated.evaluation as JsonRecord;
    expect(evaluation.overallScore).toBeGreaterThanOrEqual(0);
    expect(evaluation.overallScore).toBeLessThanOrEqual(100);
    safeCounters.chatInvocations += 1;
  }
  expect((await json<JsonRecord>(
    `/api/xunzhi/v1/interview/sessions/${sessionId}`,
  )).status).toBe("COMPLETED");

  const report = await postJson<JsonRecord>(
    `/api/xunzhi/v1/interview/sessions/${sessionId}/report`,
  );
  expect(report.status).toBe("READY");
  expect(String(report.generatedBy)).not.toMatch(/rule|fake/i);
  expect(report.resumeScore).toBe(prepared.resumeScore);
  expect((report.resumeEvaluation as JsonRecord).status).toBe("COMPLETED");
  expect(
    (report.radarData as JsonRecord[]).some((item) => item.dimension === "resume"),
  ).toBeTruthy();
  safeCounters.chatInvocations += 1;
  expect(safeCounters.chatInvocations).toBeLessThanOrEqual(12);
  expect(safeCounters.embeddingOperations).toBeLessThanOrEqual(10);

  console.log(
    `REAL_AI_SMOKE_SUMMARY ${JSON.stringify({ ...safeCounters, reportStatus: report.status })}`,
  );
  });
});
