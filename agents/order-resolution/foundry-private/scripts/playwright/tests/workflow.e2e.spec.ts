import { expect, test, type Page } from "@playwright/test";

const HIGH_RISK_DELAYED_MESSAGE =
  "Order ORD-1009 is delayed by 5 days. I need compensation.";
const LOW_RISK_LATE_MESSAGE = "Order ORD-1001 was late by one day.";
const DAMAGED_ITEM_MESSAGE = "Order ORD-1001 arrived broken.";
const caseDelayMs = Number(process.env.PLAYWRIGHT_CASE_DELAY_MS ?? 0);

async function delayForHostedModelQuota() {
  if (caseDelayMs > 0) {
    await new Promise((resolve) => setTimeout(resolve, caseDelayMs));
  }
}

async function submitWorkflowMessage(page: Page, message: string) {
  const input = page.locator("textarea").first();
  await input.fill(message);
  await page.getByRole("button", { name: "Start Workflow" }).click();
}

async function openStudioWithHealthyHistory(page: Page) {
  const historyResponse = page.waitForResponse(
    (response) => new URL(response.url()).pathname === "/api/workflows",
  );
  await page.goto("/");
  const response = await historyResponse;

  const sidebar = page.locator(".sidebar-history");
  await expect(sidebar).toBeVisible();
  await expect(sidebar.getByText("Loading workflow history...")).toBeHidden();
  await expect(sidebar.locator(".error-text")).toHaveCount(0);
  expect(new URL(response.url()).origin).toBe(new URL(page.url()).origin);
  await expect(
    page.getByText(/Unexpected token|not valid JSON|<!doctype/i),
  ).toHaveCount(0);
}

test.describe("LangGraph workflow UI", () => {
  test.beforeEach(async () => {
    await delayForHostedModelQuota();
  });

  test("high-risk request triggers HITL and approve path completes", async ({
    page,
  }) => {
    await openStudioWithHealthyHistory(page);
    const outputPanel = page.locator(".panel-output");
    const approvalPanel = page.locator(".panel-approval");

    await submitWorkflowMessage(page, HIGH_RISK_DELAYED_MESSAGE);

    await expect(
      page.getByText("hitl.request", { exact: false }),
    ).toBeVisible();
    await expect(approvalPanel.getByText("Order", { exact: true })).toBeVisible();
    await expect(approvalPanel.getByText("ord-1009", { exact: true })).toBeVisible();
    await page.locator("#approval-comment").fill("Approve delayed-order compensation");
    await page.getByRole("button", { name: "Approve" }).click();

    await expect(
      outputPanel.locator(".summary-list").getByText("completed", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("No pending approvals.", { exact: false }),
    ).toBeVisible();
  });

  test("low-risk request completes without HITL", async ({ page }) => {
    await openStudioWithHealthyHistory(page);

    await submitWorkflowMessage(page, LOW_RISK_LATE_MESSAGE);

    await expect(
      page.getByText("workflow.output", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByText("No pending approvals.", { exact: false }),
    ).toBeVisible();
  });

  test("workflow history status filter loads JSON without fallback HTML", async ({
    page,
  }) => {
    await openStudioWithHealthyHistory(page);
    const sidebar = page.locator(".sidebar-history");

    await sidebar.getByRole("combobox").selectOption("running");

    await expect(sidebar.getByText("Loading workflow history...")).toBeHidden();
    await expect(sidebar.locator(".error-text")).toHaveCount(0);
    await expect(
      page.getByText(/Unexpected token|not valid JSON|<!doctype/i),
    ).toHaveCount(0);
  });

  test("studio hides backend override controls", async ({ page }) => {
    await openStudioWithHealthyHistory(page);
    await expect(page.getByText("Runtime:", { exact: false })).toBeVisible();
    await expect(page.getByLabel("Backend URL")).toHaveCount(0);
    await expect(page.getByLabel("Backend preset")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Apply Backend" })).toHaveCount(0);
  });

  test("new run clears selected workflow panels", async ({ page }) => {
    await openStudioWithHealthyHistory(page);
    const outputPanel = page.locator(".panel-output");
    const timelinePanel = page.locator(".panel-timeline");
    const metadataPanel = page.locator(".panel-metadata");

    await submitWorkflowMessage(page, LOW_RISK_LATE_MESSAGE);

    await expect(
      page.getByText("workflow.output", { exact: false }),
    ).toBeVisible();
    await expect(
      outputPanel.locator(".summary-list").getByText("completed", { exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "New Run" }).click();

    await expect(timelinePanel).toContainText(
      "Start a workflow or select a run to view timeline events.",
    );
    await expect(outputPanel).toContainText(
      "Start or select a workflow to view the latest output.",
    );
    await expect(metadataPanel).toContainText("No workflow selected.");
  });

  test("manual test panel runs a case and reports pass", async ({ page }) => {
    await openStudioWithHealthyHistory(page);
    const manualPanel = page.locator(".panel-manual-tests");

    await expect(manualPanel.getByText("Test Tools")).toBeVisible();
    await expect(manualPanel.locator(".manual-case")).toHaveCount(0);
    await manualPanel
      .getByRole("button", { name: "Show Manual Test Matrix" })
      .click();
    const caseCard = manualPanel.locator(".manual-case", { hasText: "ORD-1001" });
    await expect(caseCard).toBeVisible();
    await caseCard.getByRole("button", { name: "Load prompt" }).click();
    await expect(page.locator("textarea").first()).toHaveValue(
      "Order ORD-1001 arrived late by 1 day. What can you do?",
    );

    await caseCard.getByRole("button", { name: "Run case" }).click();

    await expect(caseCard.locator(".result-pass")).toBeVisible();
    await expect(caseCard).toContainText("Observed");
    await expect(caseCard).toContainText("HITL: false");
    await expect(
      page
        .locator(".panel-output .summary-list")
        .getByText("completed", { exact: true }),
    ).toBeVisible();
  });

  test("reject decision escalates workflow", async ({ page }) => {
    await openStudioWithHealthyHistory(page);
    const outputPanel = page.locator(".panel-output");
    const approvalPanel = page.locator(".panel-approval");

    await submitWorkflowMessage(page, DAMAGED_ITEM_MESSAGE);

    await expect(
      page.getByText("hitl.request", { exact: false }),
    ).toBeVisible();
    await expect(approvalPanel.getByText("ord-1001", { exact: true })).toBeVisible();
    await page.locator("#approval-comment").fill("Rejecting and escalating damaged order");
    await page.getByRole("button", { name: "Reject" }).click();

    await expect(
      outputPanel.locator(".summary-list").getByText("escalated", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("No pending approvals.", { exact: false }),
    ).toBeVisible();
  });
});
