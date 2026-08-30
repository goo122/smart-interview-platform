import { expect, test } from "@playwright/test";

const createSyntheticPdf = () => {
  const content = "BT /F1 18 Tf 72 720 Td (Synthetic resume for E2E testing) Tj ET";
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

test("completes the MVP loop with fake providers", async ({ page }) => {
  await page.addInitScript(() => {
    const revokeObjectUrl = URL.revokeObjectURL.bind(URL);
    URL.revokeObjectURL = (url: string) => {
      const count = Number(
        window.localStorage.getItem("__tts_revoke_count") || "0",
      );
      window.localStorage.setItem("__tts_revoke_count", String(count + 1));
      revokeObjectUrl(url);
    };
  });
  const unique = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  const username = `e2e_${unique}`;
  const email = `${username}@example.test`;
  const knowledgeBase = `E2E 简历 ${unique}`;

  await page.goto("/auth");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill("safe-password-123");
  await page.getByPlaceholder("再次输入密码").fill("safe-password-123");
  await page.getByRole("button", { name: "注册并开始" }).click();
  await expect(page.getByRole("button", { name: "登录进入" })).toBeVisible();

  await page.locator('input[name="username"]').fill(email);
  await page.locator('input[name="password"]').fill("safe-password-123");
  await page.getByRole("button", { name: "登录进入" }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.goto("/chat");
  await page.getByPlaceholder("新知识库名称").fill(knowledgeBase);
  await page.getByRole("button", { name: "创建知识库" }).click();
  const knowledgeBaseButton = page.getByRole("button", {
    name: new RegExp(`${knowledgeBase} (?:待上传|已就绪)$`),
  });
  await expect(knowledgeBaseButton).toBeVisible();
  await knowledgeBaseButton.click();
  const uploadResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST" &&
    response.url().includes("/knowledge-bases/") &&
    response.url().endsWith("/documents"),
  );
  await page.locator('label.upload-button input[type="file"]').setInputFiles({
    name: "synthetic-resume.pdf",
    mimeType: "application/pdf",
    buffer: createSyntheticPdf(),
  });
  const uploadResponse = await uploadResponsePromise;
  expect(uploadResponse.ok()).toBeTruthy();
  expect((await uploadResponse.json()).status).toBe("PENDING");
  await expect(
    page.getByRole("button", { name: new RegExp(`${knowledgeBase} 已就绪$`) }),
  ).toBeVisible({ timeout: 60_000 });
  await page.reload();
  await expect(page.getByText("synthetic-resume.pdf")).toBeVisible();

  const streamResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST" && response.url().includes("/chat"),
  );
  const composer = page.locator('textarea[placeholder="今天我能怎么帮助你？"]');
  await composer.fill("Synthetic resume for E2E testing");
  await composer.press("Enter");
  const streamResponse = await streamResponsePromise;
  expect(streamResponse.ok()).toBeTruthy();
  const streamBody = (await streamResponse.body()).toString("utf8");
  expect(streamBody).toContain("event: start");
  expect(streamBody).toContain("event: delta");
  expect(streamBody).toContain("event: complete");
  await expect(page.getByText("RAG 知识库模式")).toBeVisible();
  await expect(page.getByText("参考来源")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("这是开发环境的模拟回答。", { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByText("这是开发环境的模拟回答。", { exact: false })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("寻知开发测试模型", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Unknown model", { exact: true })).toHaveCount(0);

  const token = await page.evaluate(() => localStorage.getItem("token"));
  expect(token).toBeTruthy();
  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const apiUrl = (path: string) =>
    new URL(path, process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5174").toString();
  const apiGet = async (path: string) => {
    const response = await page.request.get(apiUrl(path), { headers });
    expect(response.ok()).toBeTruthy();
    return response.json() as Promise<Record<string, unknown>>;
  };
  const apiPost = async (path: string, data?: Record<string, unknown>) => {
    const response = await page.request.post(apiUrl(path), {
      headers,
      data,
    });
    return { response, body: (await response.json()) as Record<string, unknown> };
  };

  const ttsCapabilities = await apiGet(
    "/api/xunzhi/v1/speech/tts/capabilities",
  );
  expect(ttsCapabilities.available).toBe(true);
  expect(ttsCapabilities.provider).toBe("fake");
  expect(ttsCapabilities.supportedAudioFormats).toContain("wav");
  const ttsSynthesis = await apiPost(
    "/api/xunzhi/v1/xunfei/tts/synthesize",
    { text: "浏览器 TTS E2E", requestId: `tts-${unique}` },
  );
  expect(ttsSynthesis.response.ok()).toBeTruthy();
  expect(ttsSynthesis.response.headers()["content-type"]).toContain(
    "application/json",
  );
  expect(ttsSynthesis.response.headers()["cache-control"]).toBe("no-store");
  const ttsAudioBase64 = ttsSynthesis.body.audioBase64 as string;
  const ttsAudio = Buffer.from(ttsAudioBase64, "base64");
  expect(ttsAudio.subarray(0, 4).toString("ascii")).toBe("RIFF");
  expect(ttsAudio.subarray(8, 12).toString("ascii")).toBe("WAVE");
  expect(ttsSynthesis.body.contentType).toBe("audio/wav");

  const oversizedTtsResponse = await page.request.post(
    apiUrl("/api/xunzhi/v1/xunfei/tts/synthesize"),
    {
      headers,
      data: { text: "a".repeat(300_000), requestId: `tts-oversized-${unique}` },
    },
  );
  expect(oversizedTtsResponse.status()).toBe(413);

  const ttsRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/xunfei/tts/synthesize")
    ) {
      ttsRequests.push(request.url());
    }
  });

  const unauthorizedResponse = await page.request.get(
    apiUrl("/api/xunzhi/v1/ai-properties?isEnabled=1&size=100"),
  );
  expect(unauthorizedResponse.status()).toBe(401);
  expect(unauthorizedResponse.headers()["x-request-id"]).toBeTruthy();

  const aiProperties = await apiGet(
    "/api/xunzhi/v1/ai-properties?isEnabled=1&size=100",
  );
  const aiRecords = aiProperties.records as Array<Record<string, unknown>>;
  expect(aiRecords.length).toBeGreaterThan(0);
  expect(aiRecords[0]?.aiName).toBe("寻知开发测试模型");
  expect(aiRecords[0]?.modelName).toBe("fake-interview-model");
  expect(aiRecords[0]?.isEnabled).toBe(1);
  const safeMetadataJson = JSON.stringify(aiProperties).toLowerCase();
  expect(safeMetadataJson).not.toMatch(
    /apikey|apisecret|authorization|baseurl|systemprompt|safe-password|bearer\s+[a-z0-9._-]+/i,
  );
  const disabledAiProperties = await apiGet(
    "/api/xunzhi/v1/ai-properties?isEnabled=0&size=100",
  );
  expect(disabledAiProperties.records).toEqual([]);

  const knowledgeBases = await apiGet("/api/xunzhi/v1/knowledge-bases?current=1&size=50");
  const selectedBase = knowledgeBases.records.find(
    (base: Record<string, string>) => base.name === knowledgeBase,
  );
  expect(selectedBase?.id).toBeTruthy();

  const { response: createInterviewResponse, body: createdSession } = await apiPost(
    "/api/xunzhi/v1/interview/sessions",
    {
      knowledgeBaseId: selectedBase.id,
      jobTitle: "后端工程师",
      jobDescription: "负责服务端开发、稳定性建设和性能优化。",
      interviewType: "TECHNICAL",
      difficulty: "MEDIUM",
      questionCount: 3,
      requestId: `interview-${unique}`,
    },
  );
  expect(createInterviewResponse.status()).toBe(201);
  const sessionId = createdSession.sessionId as string;
  expect(sessionId).toBeTruthy();
  await expect
    .poll(async () => (await apiGet(`/api/xunzhi/v1/interview/sessions/${sessionId}`)).status, {
      timeout: 60_000,
      intervals: [500, 1000, 2000],
    })
    .toBe("READY");
  const preparedSession = await apiGet(
    `/api/xunzhi/v1/interview/sessions/${sessionId}`,
  );
  expect(preparedSession.resumeEvaluationStatus).toBe("COMPLETED");
  const resumeScore = preparedSession.resumeScore;
  expect(typeof resumeScore).toBe("number");
  expect(resumeScore as number).toBeGreaterThanOrEqual(0);
  expect(resumeScore as number).toBeLessThanOrEqual(100);
  const documents = await apiGet(
    `/api/xunzhi/v1/knowledge-bases/${selectedBase.id}/documents?current=1&size=20`,
  );
  const resumeDocument = (
    documents.records as Array<Record<string, unknown>>
  ).find(
    (item) =>
      item.originalFilename === "synthetic-resume.pdf" ||
      item.original_filename === "synthetic-resume.pdf",
  );
  expect(resumeDocument?.id).toBeTruthy();
  const previewResponse = await page.request.get(
    apiUrl(`/api/xunzhi/v1/interview/sessions/${sessionId}/resume/preview`),
    { headers },
  );
  expect(previewResponse.status()).toBe(200);
  expect(previewResponse.headers()["content-type"]).toContain("application/pdf");
  expect((await previewResponse.body()).subarray(0, 5).toString("ascii")).toBe("%PDF-");

  const resumableConversations = await apiGet(
    "/api/xunzhi/v1/interview/conversations?current=1&size=20",
  );
  const resumableRecord = (
    resumableConversations.records as Array<Record<string, unknown>>
  ).find((item) => item.sessionId === sessionId);
  expect(resumableRecord?.status).toBe("READY");
  expect(resumableRecord?.conversationTitle).toBe("后端工程师");

  await page.goto("/interview");
  const continueButton = page.getByRole("link", { name: "继续上次面试" });
  await expect(continueButton).toBeVisible();
  await continueButton.click();
  await expect(page).toHaveURL(new RegExp(`/interview/room/${sessionId}$`));

  const { response: startResponse, body: startedSession } = await apiPost(
    `/api/xunzhi/v1/interview/sessions/${sessionId}/start`,
  );
  expect(startResponse.ok()).toBeTruthy();
  expect(startedSession.status).toBe("IN_PROGRESS");

  const questionAudioButton = page
    .locator('button[aria-label="播放题目播报"], button[aria-label="暂停题目播报"]')
    .first();
  await expect(questionAudioButton).toBeVisible({ timeout: 60_000 });
  if ((await questionAudioButton.getAttribute("aria-label")) === "暂停题目播报") {
    await questionAudioButton.click();
    await expect(questionAudioButton).toHaveAttribute("aria-label", "播放题目播报");
  }
  await questionAudioButton.click();
  const audioElement = page.locator('audio[data-tts-playback="true"]');
  await expect(audioElement).toBeAttached();
  await expect
    .poll(() => audioElement.evaluate((audio) => audio.readyState), {
      timeout: 10_000,
    })
    .toBeGreaterThanOrEqual(3);
  await expect
    .poll(() => ttsRequests.length, { timeout: 10_000 })
    .toBeLessThanOrEqual(1);
  const requestsAfterFirstPlay = ttsRequests.length;
  await expect(questionAudioButton).toHaveAttribute("aria-label", /播放|暂停/);
  if ((await questionAudioButton.getAttribute("aria-label")) === "暂停题目播报") {
    await questionAudioButton.click();
  }
  await questionAudioButton.click();
  await expect.poll(() => ttsRequests.length, { timeout: 10_000 }).toBe(requestsAfterFirstPlay);

  const seenTurns = new Set<string>();
  let completedSession = false;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const session = await apiGet(`/api/xunzhi/v1/interview/sessions/${sessionId}`);
    if (session.status === "COMPLETED") {
      completedSession = true;
      break;
    }
    expect(session.status).toBe("IN_PROGRESS");

    const turn = await apiGet(
      `/api/xunzhi/v1/interview/sessions/${sessionId}/current-turn`,
    );
    const turnId = turn.turnId as string;
    if (seenTurns.has(turnId)) {
      throw new Error("Current turn did not advance");
    }
    seenTurns.add(turnId);
    expect(["PRIMARY", "FOLLOW_UP"]).toContain(turn.turnType);
    const answerRequestId = `answer-${unique}-${attempt}`;
    const answerPayload = {
      turnId,
      answer: "这是一次合成的端到端测试回答，包含方案、取舍和验证结果。",
      requestId: answerRequestId,
    };
    const { response: answerResponse, body: answerBody } = await apiPost(
      `/api/xunzhi/v1/interview/sessions/${sessionId}/answers`,
      answerPayload,
    );
    expect(answerResponse.status()).toBe(202);
    expect(answerBody.status).toBe("EVALUATING");
    await expect
      .poll(async () => (await apiGet(`/api/xunzhi/v1/interview/sessions/${sessionId}/turns/${turnId}`)).status, {
        timeout: 60_000,
        intervals: [500, 1000, 2000],
      })
      .toBe("COMPLETED");
    const evaluatedTurn = await apiGet(
      `/api/xunzhi/v1/interview/sessions/${sessionId}/turns/${turnId}`,
    );
    expect(evaluatedTurn.evaluation.overallScore).toBeGreaterThanOrEqual(0);
    expect(evaluatedTurn.evaluation.overallScore).toBeLessThanOrEqual(100);

    const { response: duplicateAnswerResponse, body: duplicateAnswer } = await apiPost(
      `/api/xunzhi/v1/interview/sessions/${sessionId}/answers`,
      answerPayload,
    );
    expect([202, 409]).toContain(duplicateAnswerResponse.status());
    if (duplicateAnswerResponse.status() === 202) {
      expect(duplicateAnswer.turnId).toBe(turnId);
    }
  }
  expect(completedSession).toBeTruthy();

  const { response: reportResponse, body: report } = await apiPost(
    `/api/xunzhi/v1/interview/sessions/${sessionId}/report`,
  );
  expect(reportResponse.ok()).toBeTruthy();
  expect(report.status).toBe("READY");
  expect(report.overallScore).toBeGreaterThanOrEqual(0);
  expect(report.radarData.length).toBeGreaterThan(0);
  expect(report.items.length).toBeGreaterThan(0);
  expect(report.resumeScore).toBe(resumeScore);
  const resumeEvaluation = report.resumeEvaluation as Record<string, unknown>;
  expect(resumeEvaluation.status).toBe("COMPLETED");
  expect(resumeEvaluation.evaluationVersion).toBeTruthy();
  expect(
    (report.radarData as Array<Record<string, unknown>>).some(
      (point) => point.dimension === "resume",
    ),
  ).toBeTruthy();
  const reports = await apiGet("/api/xunzhi/v1/interview/reports?current=1&size=20");
  expect(reports.records.some((item: Record<string, string>) => item.sessionId === sessionId)).toBeTruthy();

  const revokedBeforeReport = await page.evaluate(() =>
    Number(localStorage.getItem("__tts_revoke_count") || "0"),
  );
  await page.goto(`/interview/report?sessionId=${encodeURIComponent(sessionId)}`);
  await expect
    .poll(() =>
      page.evaluate(() => Number(localStorage.getItem("__tts_revoke_count") || "0")),
    )
    .toBeGreaterThan(revokedBeforeReport);
  await expect(page.getByText("简历得分", { exact: true })).toBeVisible();
  await expect(page.getByText(String(resumeScore), { exact: true }).first()).toBeVisible();
  await expect(page.getByText("简历匹配度", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "用户菜单" }).click();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/auth$/);
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/auth$/);
});
