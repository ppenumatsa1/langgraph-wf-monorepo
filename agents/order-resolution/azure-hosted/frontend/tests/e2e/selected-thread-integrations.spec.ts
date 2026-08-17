import { expect, test } from "@playwright/test";

const threadId = "thread-e2e-selected";
const now = "2026-08-06T22:12:39.579Z";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/health", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        service: "order-resolution",
        workflow_mode: "langgraph",
        runtime_provider: "local",
        runtime_mode: "test",
        environment: "test",
      }),
    });
  });
  await page.route("**/api/workflows?*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            thread_id: threadId,
            status: "completed",
            input_summary: "Order ORD-1001 was late by one day.",
            created_at: now,
            updated_at: now,
          },
        ],
        page: 1,
        page_size: 10,
        total: 1,
      }),
    });
  });
  await page.route(`**/api/workflows/${threadId}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        thread_id: threadId,
        status: "completed",
        input: "Order ORD-1001 was late by one day.",
        events: [
          {
            id: "event-output",
            type: "workflow.output",
            thread_id: threadId,
            timestamp: now,
            payload: { message: "Resolution complete", status: "resolved" },
          },
        ],
        pending_approvals: [],
        latest_output: { message: "Resolution complete", status: "resolved" },
        metadata: {
          thread_id: threadId,
          status: "completed",
          started_at: now,
          completed_at: now,
          duration_ms: 1,
        },
      }),
    });
  });
  await page.route(`**/api/chat/stream/${threadId}/ag-ui`, async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "AG-UI is not deployed" }),
    });
  });
});

test("optional AG-UI failure leaves selected-thread controls and native timeline available", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.locator("cpk-web-inspector")).toHaveCount(0);
  await expect(page.getByTestId("ag-ui-thread-view")).toContainText(
    "AG-UI Selected Thread",
  );
  await expect(page.getByTestId("copilot-thread-assistant")).toContainText(
    "Selected Thread Assistant",
  );
  await expect(page.getByText("workflow.output", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Connect AG-UI" }).click();

  await expect(page.getByRole("status")).toContainText(
    "The optional AG-UI endpoint returned 404.",
  );
  await expect(page.locator(".panel-timeline")).toContainText("workflow.output");
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
});

test("durable AG-UI view uses the selected thread GET stream", async ({ page }) => {
  await page.unroute(`**/api/chat/stream/${threadId}/ag-ui`);
  await page.route(`**/api/chat/stream/${threadId}/ag-ui`, async (route) => {
    expect(route.request().method()).toBe("GET");
    await route.fulfill({
      contentType: "text/event-stream",
      body: [
        `data: {"type":"RUN_STARTED","threadId":"${threadId}","runId":"${threadId}"}\n\n`,
        'data: {"type":"STEP_STARTED","stepName":"triage"}\n\n',
        `data: {"type":"RUN_FINISHED","threadId":"${threadId}","runId":"${threadId}"}\n\n`,
      ].join(""),
    });
  });

  await page.goto("/");
  const request = page.waitForRequest(
    (candidate) =>
      new URL(candidate.url()).pathname === `/api/chat/stream/${threadId}/ag-ui`,
  );
  await page.getByRole("button", { name: "Connect AG-UI" }).click();

  expect((await request).method()).toBe("GET");
  await expect(page.getByLabel("AG-UI protocol frames")).toContainText("RUN_STARTED");
  await expect(page.getByLabel("AG-UI protocol frames")).toContainText("STEP_STARTED");
  await expect(page.getByLabel("AG-UI protocol frames")).toContainText("RUN_FINISHED");
});

test("CopilotKit bridge posts selected-thread AG-UI input to the root endpoint", async ({
  page,
}) => {
  const requests: Array<Record<string, unknown>> = [];
  await page.route("**/api/copilotkit", async (route) => {
    expect(route.request().method()).toBe("POST");
    requests.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      contentType: "text/event-stream",
      body: [
        `data: {"type":"RUN_STARTED","threadId":"${threadId}","runId":"${threadId}"}\n\n`,
        'data: {"type":"TEXT_MESSAGE_START","messageId":"assistant-response","role":"assistant"}\n\n',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"assistant-response","delta":"The selected thread is completed."}\n\n',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"assistant-response"}\n\n',
        `data: {"type":"RUN_FINISHED","threadId":"${threadId}","runId":"${threadId}"}\n\n`,
      ].join(""),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Load assistant view" }).click();

  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0]).toEqual({ threadId });
  await expect(page.getByLabel("CopilotKit assistant frames")).toContainText("RUN_STARTED");
  await expect(page.getByLabel("CopilotKit assistant frames")).toContainText(
    "TEXT_MESSAGE_CONTENT",
  );
  await expect(page.getByLabel("CopilotKit assistant frames")).toContainText(
    "The selected thread is completed.",
  );
  await expect(page.getByLabel("CopilotKit assistant frames")).toContainText("RUN_FINISHED");
});
