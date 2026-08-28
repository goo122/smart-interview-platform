import { expect, test } from "@playwright/test";

const createSyntheticPdf = () => {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    "<< /Length 62 >>\nstream\nBT /F1 18 Tf 72 720 Td (Synthetic resume for E2E testing) Tj ET\nendstream",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xrefOffset = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  offsets.slice(1).forEach((offset) => { pdf += `${String(offset).padStart(10, "0")} 00000 n \n`; });
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  return Buffer.from(pdf, "ascii");
};

test("completes the MVP loop with fake providers", async ({ page }) => {
  const unique = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  const username = `e2e_${unique}`;
  const email = `${username}@example.test`;
  const knowledgeBase = `E2E 简历 ${unique}`;

  await page.goto("/auth");
  await page.getByRole("tab", { name: "注册" }).click();
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("safe-password-123");
  await page.getByLabel("确认密码").fill("safe-password-123");
  await page.getByRole("button", { name: "注册并开始" }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.getByRole("button", { name: "退出" }).click();
  await expect(page).toHaveURL(/\/auth$/);
  await page.getByLabel("邮箱或用户名").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("safe-password-123");
  await page.getByRole("button", { name: "登录进入" }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.goto("/chat");
  await page.getByPlaceholder("新知识库名称").fill(knowledgeBase);
  await page.getByRole("button", { name: "+ 创建知识库" }).click();
  await expect(page.getByRole("button", { name: new RegExp(knowledgeBase) })).toBeVisible();
  await page.getByRole("button", { name: new RegExp(knowledgeBase) }).click();
  await page.locator('label.upload-button input[type="file"]').setInputFiles({
    name: "synthetic-resume.pdf",
    mimeType: "application/pdf",
    buffer: createSyntheticPdf(),
  });
  await expect(page.getByText("已就绪")).toBeVisible({ timeout: 60_000 });
  await page.reload();
  await expect(page.getByText("synthetic-resume.pdf")).toBeVisible();

  await page.getByLabel("知识库").selectOption({ label: knowledgeBase });
  const streamResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST" && response.url().includes("/chat"),
  );
  await page.locator('textarea[placeholder^="输入你的问题"]').fill("请根据简历总结我的技术经历");
  await page.getByRole("button", { name: "发送" }).click();
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

  await page.goto("/interview");
  await page.getByLabel("简历知识库").selectOption({ label: knowledgeBase });
  await page.getByLabel("岗位名称").fill("后端工程师");
  await page.getByLabel("岗位描述").fill("负责服务端开发、稳定性建设和性能优化。");
  await page.getByRole("button", { name: "创建面试" }).click();
  await expect(page).toHaveURL(/\/interview\/[^/]+$/);
  await expect(page.getByRole("button", { name: "开始面试" })).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "开始面试" }).click();
  await expect(page.getByText("PRIMARY · 基础题")).toBeVisible({ timeout: 30_000 });

  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (await page.getByText("面试完成").isVisible().catch(() => false)) break;
    const editor = page.locator('textarea[placeholder^="写下你的回答"]');
    await expect(editor).toBeVisible({ timeout: 30_000 });
    await editor.fill("这是一次合成的端到端测试回答，包含方案、取舍和验证结果。");
    await page.getByRole("button", { name: "提交回答" }).click();
    await expect(page.getByText(/正在评分|PRIMARY · 基础题|FOLLOW_UP · 动态追问|面试完成/).first()).toBeVisible({ timeout: 60_000 });
  }
  await expect(page.getByText("面试完成")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: "生成面试报告" }).click();
  await expect(page).toHaveURL(/\/interview\/reports\/[^/]+$/, { timeout: 60_000 });
  await expect(page.getByText("能力雷达")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("问答回放")).toBeVisible();
  await page.reload();
  await expect(page.getByText("面试报告")).toBeVisible({ timeout: 30_000 });
  await page.goto("/interview/reports");
  await expect(page.getByText("后端工程师")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "退出" }).click();
  await expect(page).toHaveURL(/\/auth$/);
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/auth$/);
});
