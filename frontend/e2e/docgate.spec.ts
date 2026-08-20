import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
const root = path.resolve(__dirname, "../..");
function ids() {
  return JSON.parse(
    readFileSync(path.join(root, "test-results/e2e-sessions.json"), "utf-8"),
  ) as { accept: string; rework: string };
}
async function decideTasks(
  page: import("@playwright/test").Page,
  first: string,
  rest: string,
) {
  const cards = page.locator("[data-testid^=task-]");
  await expect(cards.first()).toBeVisible();
  const count = await cards.count();
  for (let i = 0; i < count; i++) {
    const card = cards.nth(i);
    const selected = i === 0 ? first : rest;
    await card.getByLabel("决定").selectOption(selected);
    await card.getByRole("button", { name: "保存决定" }).click();
    await expect(card.getByRole("status")).toContainText(`已保存：${selected}`);
  }
}
async function acceptAllHunks(page: import("@playwright/test").Page) {
  const buttons = page.getByRole("button", { name: "接受此修改" });
  await expect(buttons.first()).toBeVisible();
  const count = await buttons.count();
  for (let i = 0; i < count; i++) {
    await buttons.nth(i).click();
    await expect(page.getByText("已决定：accepted").nth(i)).toBeVisible();
  }
}
test("list loading, empty and error states are actionable", async ({
  page,
}) => {
  await page.route("**/api/v1/sessions", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"sessions":[]}',
    }),
  );
  await page.goto("/sessions");
  await expect(page.getByText("还没有会话")).toBeVisible();
  await page.unroute("**/api/v1/sessions");
  await page.route("**/api/v1/sessions", (route) => route.abort());
  await page.reload();
  await expect(page.locator(".error[role=alert]")).toContainText("无法加载");
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
});
test("accept gate, evidence, refresh and API restart recovery", async ({
  page,
}) => {
  const id = ids().accept;
  await page.goto(`/sessions/${id}`);
  await expect(page.getByText("Agent 声明（不可信）").first()).toBeVisible();
  await expect(page.getByText("机器检查（确定性证据）").first()).toBeVisible();
  await page.getByRole("button", { name: "接受会话" }).click();
  await expect(page.getByRole("status").last()).toContainText(
    "ACCEPTANCE_BLOCKED",
  );
  await decideTasks(page, "accepted", "accepted");
  await acceptAllHunks(page);
  await page.reload();
  await expect(page.getByText("已保存：accepted").first()).toBeVisible();
  const child = spawn(
    path.join(root, ".venv/bin/uvicorn"),
    [
      "app.main:app",
      "--app-dir",
      path.join(root, "backend"),
      "--host",
      "127.0.0.1",
      "--port",
      "8766",
    ],
    {
      env: {
        ...process.env,
        DOCGATE_WORKSPACE_ROOT: path.join(root, "test-results/e2e-workspace"),
      },
      stdio: "ignore",
    },
  );
  try {
    await expect
      .poll(async () => {
        try {
          return (await fetch(`http://127.0.0.1:8766/api/v1/sessions/${id}`))
            .status;
        } catch {
          return 0;
        }
      })
      .toBe(200);
  } finally {
    child.kill("SIGTERM");
  }
  await page.getByRole("button", { name: "接受会话" }).click();
  await expect(page.getByRole("status").last()).toContainText("会话已接受");
  await expect(page.getByRole("button", { name: "接受会话" })).toBeDisabled();
});
test("rework includes only failed items and creates a new round", async ({
  page,
}) => {
  const id = ids().rework;
  await page.goto(`/sessions/${id}`);
  await decideTasks(page, "rework_requested", "accepted");
  await acceptAllHunks(page);
  await page.getByRole("button", { name: "生成返工包" }).click();
  await expect(page.getByText(/第 2 轮 · agent_working/)).toBeVisible();
  await expect(page.locator("[data-testid^=task-]")).toHaveCount(1);
  await expect(page.getByRole("status").last()).toContainText("返工包已生成");
});
