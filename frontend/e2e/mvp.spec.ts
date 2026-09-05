import { expect, test } from "@playwright/test";

const createSyntheticPdf = () => {
  const content =
    "BT /F1 18 Tf 72 720 Td (Synthetic resume for E2E testing) Tj ET";
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

test("completes the MVP loop with fake providers", async ({ page }, testInfo) => {
  test.setTimeout(240_000);
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
  const uploadResponsePromise = page.waitForResponse(
    (response) =>
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

  const streamResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/chat"),
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
  await expect(
    page.getByText("这是开发环境的模拟回答。", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("这是开发环境的模拟回答。", { exact: false }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText("寻知开发测试模型", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("Unknown model", { exact: true })).toHaveCount(0);

  const token = await page.evaluate(() => localStorage.getItem("token"));
  expect(token).toBeTruthy();
  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const apiOrigin = new URL(page.url()).origin;
  const apiUrl = (path: string) => new URL(path, apiOrigin).toString();
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
    return {
      response,
      body: (await response.json()) as Record<string, unknown>,
    };
  };

  const ttsCapabilities = await apiGet(
    "/api/xunzhi/v1/speech/tts/capabilities",
  );
  expect(ttsCapabilities.available).toBe(true);
  expect(ttsCapabilities.provider).toBe("fake");
  expect(ttsCapabilities.supportedAudioFormats).toContain("wav");
  const ttsSynthesis = await apiPost("/api/xunzhi/v1/xunfei/tts/synthesize", {
    text: "浏览器 TTS E2E",
    requestId: `tts-${unique}`,
  });
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

  const knowledgeBases = await apiGet(
    "/api/xunzhi/v1/knowledge-bases?current=1&size=50",
  );
  const selectedBase = knowledgeBases.records.find(
    (base: Record<string, string>) => base.name === knowledgeBase,
  );
  expect(selectedBase?.id).toBeTruthy();

  const { response: createInterviewResponse, body: createdSession } =
    await apiPost("/api/xunzhi/v1/interview/sessions", {
      knowledgeBaseId: selectedBase.id,
      jobTitle: "后端工程师",
      jobDescription: "负责服务端开发、稳定性建设和性能优化。",
      interviewType: "TECHNICAL",
      difficulty: "MEDIUM",
      questionCount: 3,
      requestId: `interview-${unique}`,
    });
  expect(createInterviewResponse.status()).toBe(201);
  expect(createdSession.status).toBe("PREPARING");
  const sessionId = createdSession.sessionId as string;
  expect(sessionId).toBeTruthy();
  await expect
    .poll(
      async () =>
        (await apiGet(`/api/xunzhi/v1/interview/sessions/${sessionId}`)).status,
      {
        timeout: 60_000,
        intervals: [500, 1000, 2000],
      },
    )
    .toBe("READY");
  await expect
    .poll(
      async () =>
        (
          await apiGet(`/api/xunzhi/v1/interview/sessions/${sessionId}`)
        ).resumeEvaluationStatus,
      {
        timeout: 60_000,
        intervals: [500, 1000, 2000],
      },
    )
    .toBe("COMPLETED");
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
  expect(previewResponse.headers()["content-type"]).toContain(
    "application/pdf",
  );
  expect((await previewResponse.body()).subarray(0, 5).toString("ascii")).toBe(
    "%PDF-",
  );

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
    .locator(
      'button[aria-label="播放题目播报"], button[aria-label="暂停题目播报"]',
    )
    .first();
  await expect(questionAudioButton).toBeVisible({ timeout: 60_000 });
  if (
    (await questionAudioButton.getAttribute("aria-label")) === "暂停题目播报"
  ) {
    await questionAudioButton.press("Enter");
    await expect(questionAudioButton).toHaveAttribute(
      "aria-label",
      "播放题目播报",
    );
  }
  await questionAudioButton.press("Enter");
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
  if (
    (await questionAudioButton.getAttribute("aria-label")) === "暂停题目播报"
  ) {
    await questionAudioButton.press("Enter");
  }
  await questionAudioButton.press("Enter");
  await expect
    .poll(() => ttsRequests.length, { timeout: 10_000 })
    .toBe(requestsAfterFirstPlay);

  const seenTurns = new Set<string>();
  let previousTurn: Record<string, unknown> | null = null;
  let followUps = 0;
  let completedSession = false;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const session = await apiGet(
      `/api/xunzhi/v1/interview/sessions/${sessionId}`,
    );
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
    if (turn.turnType === "FOLLOW_UP") {
      followUps += 1;
      expect(turn.parentTurnId).toBe(previousTurn?.turnId);
    }
    previousTurn = turn;
    const answerComposer = page.getByPlaceholder("输入你的回答，或点击麦克风开始语音作答...");
    await expect(answerComposer).toBeEnabled();
    await expect(page.getByText(turn.question as string, { exact: false }).last()).toBeVisible();

    if (attempt === 1) {
      // Lose a read after a reload; recovery must not POST the already saved answer.
      let loseReads = true;
      const currentPath = `**/sessions/${sessionId}/current-turn`;
      await page.route(currentPath, (route) => loseReads ? route.abort("internetdisconnected") : route.continue());
      await page.reload();
      await expect(page.getByRole("button", { name: "重新同步面试" })).toBeVisible();
      await expect(answerComposer).toBeDisabled();
      loseReads = false;
      await page.getByRole("button", { name: "重新同步面试" }).click();
      await expect(answerComposer).toBeEnabled();
      await expect(page.getByText(turn.question as string, { exact: false }).last()).toBeVisible();
      await page.unroute(currentPath);
    }

    const answerResponsePromise = page.waitForResponse(
      (response) => response.request().method() === "POST" && response.url().endsWith(`/sessions/${sessionId}/answers`),
    );
    const nextResponsePromise = attempt === 2
      ? page.waitForResponse((response) => response.url().endsWith(`/sessions/${sessionId}/current-turn`) && response.ok())
      : null;
    await answerComposer.fill("这是一次合成的端到端测试回答，包含方案、取舍和验证结果。");
    await answerComposer.press("Enter");
    const answerResponse = await answerResponsePromise;
    const answerBody = await answerResponse.json();
    const answerPayload = answerResponse.request().postDataJSON();
    expect(answerResponse.status()).toBe(202);
    expect(answerBody.status).toBe("EVALUATING");
    if (attempt === 0) {
      // Replay the accepted EVALUATING snapshot to hold a deterministic refresh
      // boundary even when the fake worker completes before the browser reloads.
      const currentPath = `**/sessions/${sessionId}/current-turn`;
      let replayEvaluating = true;
      await page.route(currentPath, (route) => replayEvaluating
        ? route.fulfill({ json: { ...turn, status: answerBody.status, canAnswer: false } })
        : route.continue());
      const restoringResponse = page.waitForResponse((response) => response.url().endsWith(`/sessions/${sessionId}/current-turn`));
      await page.reload();
      await restoringResponse;
      await expect(answerComposer).toBeDisabled();
      await expect(page.getByText("正在同步面试进度，等待当前题目准备完成…")).toBeVisible();
      replayEvaluating = false;
      await expect(answerComposer).toBeEnabled();
      await page.unroute(currentPath);
    }
    if (nextResponsePromise) {
      const nextResponse = await nextResponsePromise;
      const nextQuestion = (await nextResponse.json()).question as string;
      const visibleDelayMs = await page.evaluate(({ question, path }) => new Promise<number>((resolve) => {
        const observer = new MutationObserver(check);
        function check() {
          if (!document.body.textContent?.includes(question)) return;
          const timings = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
          const response = timings.filter((entry) => entry.name.endsWith(path)).at(-1);
          if (!response) return;
          observer.disconnect();
          resolve(performance.now() - response.responseEnd);
        }
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });
        check();
      }), { question: nextQuestion, path: `/sessions/${sessionId}/current-turn` });
      await testInfo.attach("question-display-latency", {
        body: JSON.stringify({ provider: "fake", response_to_visible_upper_bound_ms: visibleDelayMs }),
        contentType: "application/json",
      });
      console.log(`Question response to visible (upper bound): ${visibleDelayMs.toFixed(1)} ms`);
    }
    await expect
      .poll(
        async () =>
          (
            await apiGet(
              `/api/xunzhi/v1/interview/sessions/${sessionId}/turns/${turnId}`,
            )
          ).status,
        {
          timeout: 60_000,
          intervals: [500, 1000, 2000],
        },
      )
      .toBe("COMPLETED");
    const evaluatedTurn = await apiGet(
      `/api/xunzhi/v1/interview/sessions/${sessionId}/turns/${turnId}`,
    );
    expect(evaluatedTurn.evaluation.overallScore).toBeGreaterThanOrEqual(0);
    expect(evaluatedTurn.evaluation.overallScore).toBeLessThanOrEqual(100);

    const { response: duplicateAnswerResponse, body: duplicateAnswer } =
      await apiPost(
        `/api/xunzhi/v1/interview/sessions/${sessionId}/answers`,
        answerPayload,
      );
    expect([202, 409]).toContain(duplicateAnswerResponse.status());
    if (duplicateAnswerResponse.status() === 202) {
      expect(duplicateAnswer.turnId).toBe(turnId);
    }
  }
  expect(completedSession).toBeTruthy();
  expect(followUps).toBeGreaterThan(0);
  const savedTurns = await apiGet(`/api/xunzhi/v1/interview/sessions/${sessionId}/turns`);
  expect(savedTurns).toHaveLength(seenTurns.size);
  expect(savedTurns.every((turn: Record<string, unknown>) =>
    turn.status === "COMPLETED" && turn.answer === "这是一次合成的端到端测试回答，包含方案、取舍和验证结果。",
  )).toBe(true);
  // The completed session has no current turn. Reopening must still offer its report.
  await page.reload();
  await expect(page.getByText("面试已结束", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看报告", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "查看报告", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/interview/report\\?sessionId=${sessionId}$`));

  const { response: reportStartResponse, body: reportStart } = await apiPost(
    `/api/xunzhi/v1/interview/sessions/${sessionId}/report`,
  );
  expect(reportStartResponse.ok()).toBeTruthy();
  expect([200, 202]).toContain(reportStartResponse.status());
  expect(["PENDING", "GENERATING", "READY"]).toContain(reportStart.status);
  await expect
    .poll(
      async () =>
        (await apiGet(`/api/xunzhi/v1/interview/sessions/${sessionId}/report`))
          .status,
      {
        timeout: 60_000,
        intervals: [500, 1000, 2000],
      },
    )
    .toBe("READY");
  const report = await apiGet(
    `/api/xunzhi/v1/interview/sessions/${sessionId}/report`,
  );
  expect(report.status).toBe("READY");
  expect(report.overallScore).toBeGreaterThanOrEqual(0);
  expect(report.radarData.length).toBeGreaterThan(0);
  expect(report.items.length).toBe(seenTurns.size);
  expect(report.resumeScore).toBe(resumeScore);
  const resumeEvaluation = report.resumeEvaluation as Record<string, unknown>;
  expect(resumeEvaluation.status).toBe("COMPLETED");
  expect(resumeEvaluation.evaluationVersion).toBeTruthy();
  expect(
    (report.radarData as Array<Record<string, unknown>>).some(
      (point) => point.dimension === "resume",
    ),
  ).toBeTruthy();
  const reports = await apiGet(
    "/api/xunzhi/v1/interview/reports?current=1&size=20",
  );
  expect(
    reports.records.some(
      (item: Record<string, string>) => item.sessionId === sessionId,
    ),
  ).toBeTruthy();

  await page.goto(
    `/interview/report?sessionId=${encodeURIComponent(sessionId)}`,
  );
  await expect
    .poll(() =>
      page.evaluate(() =>
        Number(localStorage.getItem("__tts_revoke_count") || "0"),
      ),
    )
    .toBeGreaterThan(0);
  await expect(page.getByText("简历得分", { exact: true })).toBeVisible();
  await expect(
    page.getByText(String(resumeScore), { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("简历匹配度", { exact: true }).first(),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("简历得分", { exact: true })).toBeVisible();
  await expect(
    page.getByText(String(resumeScore), { exact: true }).first(),
  ).toBeVisible();

  const { response: earlyCreateResponse, body: earlyCreatedSession } =
    await apiPost("/api/xunzhi/v1/interview/sessions", {
      knowledgeBaseId: selectedBase.id,
      jobTitle: "后端工程师",
      jobDescription: "负责服务端开发、稳定性建设和性能优化。",
      interviewType: "TECHNICAL",
      difficulty: "MEDIUM",
      questionCount: 3,
      requestId: `interview-early-${unique}`,
    });
  expect(earlyCreateResponse.status()).toBe(201);
  expect(earlyCreatedSession.status).toBe("PREPARING");
  const earlySessionId = earlyCreatedSession.sessionId as string;
  await expect
    .poll(
      async () =>
        (await apiGet(`/api/xunzhi/v1/interview/sessions/${earlySessionId}`))
          .status,
      {
        timeout: 60_000,
        intervals: [500, 1000, 2000],
      },
    )
    .toBe("READY");

  await page.goto(`/interview/room/${earlySessionId}`);
  const { response: earlyStartResponse, body: earlyStartedSession } =
    await apiPost(`/api/xunzhi/v1/interview/sessions/${earlySessionId}/start`);
  expect(earlyStartResponse.ok()).toBeTruthy();
  expect(earlyStartedSession.status).toBe("IN_PROGRESS");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "结束面试", exact: true }),
  ).toBeVisible();

  const earlyTurn = await apiGet(
    `/api/xunzhi/v1/interview/sessions/${earlySessionId}/current-turn`,
  );
  const earlyTurnId = earlyTurn.turnId as string;
  const earlyComposer = page.locator(
    'textarea[placeholder="输入你的回答，或点击麦克风开始语音作答..."]',
  );
  await earlyComposer.fill("这是提前结束流程的测试回答。");
  await earlyComposer.press("Enter");
  await expect
    .poll(
      async () =>
        (
          await apiGet(
            `/api/xunzhi/v1/interview/sessions/${earlySessionId}/turns/${earlyTurnId}`,
          )
        ).status,
      {
        timeout: 60_000,
        intervals: [500, 1000, 2000],
      },
    )
    .toBe("COMPLETED");

  const finishResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/sessions/${earlySessionId}/finish`),
  );
  await page.getByRole("button", { name: "结束面试", exact: true }).click();
  const finishResponse = await finishResponsePromise;
  expect(finishResponse.ok()).toBeTruthy();
  await expect(page).toHaveURL(
    new RegExp(`/interview/report\\?sessionId=${earlySessionId}$`),
  );
  await expect(page.getByText("面试表现报告", { exact: true })).toBeVisible();
  await expect(page.getByText("简历得分", { exact: true })).toBeVisible({
    timeout: 60_000,
  });
  await page.screenshot({ path: testInfo.outputPath("completed-report.png"), fullPage: true });

  await page.goto("/interview/room/00000000-0000-4000-8000-000000000000");
  await expect(page.getByText("面试不存在或无权访问，请返回面试列表。", { exact: true })).toBeVisible();
  await expect(page.getByPlaceholder("输入你的回答，或点击麦克风开始语音作答...")).toBeDisabled();
  await page.getByRole("link", { name: "返回面试列表" }).click();
  await expect(page).toHaveURL(/\/interview$/);

  await page.getByRole("button", { name: "用户菜单" }).click();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/auth$/);
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/auth$/);
});
