import { useState } from "react";

import { MANUAL_CASES } from "../../data/manualCases";
import { fetchApiJson } from "../../lib/apiClient";
import { redactWorkflowRunDetails } from "../../lib/workflowPrivacy";
import type { ManualCase } from "../../data/manualCases";
import type { WorkflowEvent, WorkflowRunDetails } from "../../types/workflow";
import StatusBadge from "./StatusBadge";

const TERMINAL_STATUSES = new Set(["completed", "failed", "escalated"]);

type CaseResult = {
  caseId: string;
  threadId: string | null;
  status: "idle" | "running" | "pass" | "fail";
  observedStatus?: string;
  observedHitl?: boolean;
  evidenceCount?: number;
  failures: string[];
};

type Props = {
  apiBase: string;
  onLoadPrompt: (prompt: string) => void;
  onOpenWorkflow: (threadId: string) => Promise<void>;
};

function eventTypes(details: WorkflowRunDetails): string[] {
  return details.events.map((event) => event.type);
}

function containsValue(value: unknown, expected: string): boolean {
  if (typeof value === "string") {
    return value.includes(expected);
  }
  if (Array.isArray(value)) {
    return value.some((item) => containsValue(item, expected));
  }
  if (value && typeof value === "object") {
    return Object.values(value).some((nested) => containsValue(nested, expected));
  }
  return false;
}

function evidenceCount(events: WorkflowEvent[]): number {
  return events.reduce((count, event) => {
    if (
      event.type === "tool.call" &&
      typeof event.payload.evidence_count === "number"
    ) {
      return Math.max(count, event.payload.evidence_count);
    }
    return count;
  }, 0);
}

async function waitForProgress(
  apiBase: string,
  threadId: string,
): Promise<WorkflowRunDetails> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const latest = redactWorkflowRunDetails(
      await fetchApiJson<WorkflowRunDetails>(
        apiBase,
        `/api/workflows/${encodeURIComponent(threadId)}`,
      ),
    );
    if (
      TERMINAL_STATUSES.has(latest.status) ||
      latest.status === "waiting_approval"
    ) {
      return latest;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 750));
  }
  throw new Error(`Timed out waiting for workflow ${threadId}`);
}

async function waitForTerminal(
  apiBase: string,
  threadId: string,
): Promise<WorkflowRunDetails> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const latest = redactWorkflowRunDetails(
      await fetchApiJson<WorkflowRunDetails>(
        apiBase,
        `/api/workflows/${encodeURIComponent(threadId)}`,
      ),
    );
    if (TERMINAL_STATUSES.has(latest.status)) {
      return latest;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 750));
  }
  throw new Error(`Timed out waiting for terminal workflow ${threadId}`);
}

function evaluateCase(testCase: ManualCase, details: WorkflowRunDetails): string[] {
  const failures: string[] = [];
  const types = new Set(eventTypes(details));
  const observedHitl = types.has("hitl.request");

  if (details.status !== testCase.expected_status) {
    failures.push(
      `status expected ${testCase.expected_status}, observed ${details.status}`,
    );
  }
  if (observedHitl !== testCase.expect_hitl) {
    failures.push(
      `HITL expected ${testCase.expect_hitl}, observed ${observedHitl}`,
    );
  }
  for (const eventType of testCase.required_events ?? []) {
    if (!types.has(eventType)) {
      failures.push(`missing event ${eventType}`);
    }
  }
  for (const eventType of testCase.forbidden_events ?? []) {
    if (types.has(eventType)) {
      failures.push(`forbidden event ${eventType} was emitted`);
    }
  }
  if (
    testCase.expected_order_id &&
    !containsValue(details, testCase.expected_order_id)
  ) {
    failures.push(`expected order id ${testCase.expected_order_id} not found`);
  }

  return failures;
}

export default function ManualTestPanel({
  apiBase,
  onLoadPrompt,
  onOpenWorkflow,
}: Props) {
  const [results, setResults] = useState<Record<string, CaseResult>>({});
  const [runningAll, setRunningAll] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const updateResult = (caseId: string, result: Partial<CaseResult>) => {
    setResults((current) => ({
      ...current,
      [caseId]: {
        caseId,
        threadId: current[caseId]?.threadId ?? null,
        status: current[caseId]?.status ?? "idle",
        failures: current[caseId]?.failures ?? [],
        ...result,
      },
    }));
  };

  const runCase = async (testCase: ManualCase) => {
    updateResult(testCase.id, {
      status: "running",
      threadId: null,
      failures: [],
      observedStatus: undefined,
      observedHitl: undefined,
      evidenceCount: undefined,
    });

    try {
      const startResponse = await fetchApiJson<{ thread_id: string }>(
        apiBase,
        "/api/chat/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: testCase.prompt,
            session_id: testCase.session_id,
          }),
        },
      );
      let details = await waitForProgress(apiBase, startResponse.thread_id);
      if (testCase.decision) {
        const approval = details.pending_approvals[0];
        if (!approval) {
          throw new Error("expected pending HITL approval but found none");
        }
        await fetchApiJson<unknown>(
          apiBase,
          "/api/hitl/respond",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              checkpoint_id: approval.checkpoint_id,
              decision: testCase.decision,
              reviewer: "manual-test-panel",
              comments: `${testCase.decision} by Workflow Studio manual test panel`,
            }),
          },
          { allowNoContent: true },
        );
        details = await waitForTerminal(apiBase, startResponse.thread_id);
      } else if (!TERMINAL_STATUSES.has(details.status)) {
        details = await waitForTerminal(apiBase, startResponse.thread_id);
      }

      const failures = evaluateCase(testCase, details);
      const observedHitl = eventTypes(details).includes("hitl.request");
      updateResult(testCase.id, {
        status: failures.length === 0 ? "pass" : "fail",
        threadId: startResponse.thread_id,
        observedStatus: details.status,
        observedHitl,
        evidenceCount: evidenceCount(details.events),
        failures,
      });
      await onOpenWorkflow(startResponse.thread_id);
    } catch (error) {
      updateResult(testCase.id, {
        status: "fail",
        failures: [error instanceof Error ? error.message : "Unexpected error"],
      });
    }
  };

  const runAll = async () => {
    setRunningAll(true);
    try {
      for (const testCase of MANUAL_CASES) {
        await runCase(testCase);
      }
    } finally {
      setRunningAll(false);
    }
  };

  return (
    <section className={`panel panel-manual-tests${expanded ? " expanded" : ""}`}>
      <header className="panel-head">
        <div>
          <h2>Test Tools</h2>
          <p className="muted">
            Manual Test Matrix is collapsed by default because it is for demos,
            smoke checks, and parity validation, not regular workflow use.
          </p>
        </div>
        <div className="manual-test-toolbar">
          {expanded ? (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={runningAll}
              onClick={() => void runAll()}
            >
              {runningAll ? "Running..." : "Run all"}
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-secondary manual-test-toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Hide Manual Test Matrix" : "Show Manual Test Matrix"}
          </button>
        </div>
      </header>

      {expanded ? (
        <div className="manual-case-list" aria-label="Manual Test Matrix">
        {MANUAL_CASES.map((testCase) => {
          const result = results[testCase.id];
          return (
            <article className="manual-case" key={testCase.id}>
              <div className="manual-case-main">
                <div>
                  <div className="manual-case-title">
                    <strong>{testCase.id}</strong>
                    <span className={`result-badge result-${result?.status ?? "idle"}`}>
                      {result?.status ?? "idle"}
                    </span>
                  </div>
                  <p>{testCase.prompt}</p>
                  <div className="manual-case-expectations">
                    <span>Expected: {testCase.expected_status}</span>
                    <span>HITL: {String(testCase.expect_hitl)}</span>
                    {testCase.decision ? <span>Decision: {testCase.decision}</span> : null}
                    {result?.evidenceCount !== undefined ? (
                      <span>Evidence: {result.evidenceCount}</span>
                    ) : null}
                  </div>
                </div>
                <div className="manual-case-actions">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={result?.status === "running" || runningAll}
                    onClick={() => onLoadPrompt(testCase.prompt)}
                  >
                    Load prompt
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={result?.status === "running" || runningAll}
                    onClick={() => void runCase(testCase)}
                  >
                    {result?.status === "running" ? "Running..." : "Run case"}
                  </button>
                  {result?.threadId ? (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void onOpenWorkflow(result.threadId!)}
                    >
                      View run
                    </button>
                  ) : null}
                </div>
              </div>

              {result?.observedStatus ? (
                <div className="manual-case-observed">
                  <span>Observed</span>
                  <StatusBadge status={result.observedStatus as ManualCase["expected_status"]} />
                  <span>HITL: {String(result.observedHitl)}</span>
                  {result.threadId ? <code>{result.threadId}</code> : null}
                </div>
              ) : null}

              {result?.failures.length ? (
                <ul className="manual-case-failures">
                  {result.failures.map((failure) => (
                    <li key={`${testCase.id}-${failure}`}>{failure}</li>
                  ))}
                </ul>
              ) : null}
            </article>
          );
        })}
        </div>
      ) : null}
    </section>
  );
}
