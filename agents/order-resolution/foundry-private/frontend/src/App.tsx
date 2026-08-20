import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAgentContext } from "@copilotkit/react-core/v2";
import { flushSync } from "react-dom";

import AppShell from "./components/studio/AppShell";
import AgUiThreadPanel from "./components/studio/AgUiThreadPanel";
import HumanApprovalPanel from "./components/studio/HumanApprovalPanel";
import LatestOutputPanel from "./components/studio/LatestOutputPanel";
import ManualTestPanel from "./components/studio/ManualTestPanel";
import RagEvidencePanel from "./components/studio/RagEvidencePanel";
import RunMetadataPanel from "./components/studio/RunMetadataPanel";
import SelectedThreadAssistantPanel from "./components/studio/SelectedThreadAssistantPanel";
import WorkflowHistorySidebar from "./components/studio/WorkflowHistorySidebar";
import WorkflowRunComposer from "./components/studio/WorkflowRunComposer";
import { createSafeSelectedThreadContext } from "./copilot";
import { getInitialApiBase } from "./config";
import { fetchApiJson } from "./lib/apiClient";
import { openRichThreadStream } from "./lib/sseClient";
import { redactWorkflowEvent, redactWorkflowRunDetails } from "./lib/workflowPrivacy";
import WorkflowTimeline from "./components/studio/WorkflowTimeline";
import type {
  PendingApproval,
  WorkflowEvent,
  WorkflowRunDetails,
  WorkflowRunListItem,
  WorkflowRunListResponse,
  WorkflowStatus,
} from "./types/workflow";

const DEFAULT_MESSAGE =
  "Order ORD-1009 is delayed by 5 days. I need compensation.";

type RuntimeHealth = {
  status: "ok";
  service: string;
  workflow_mode: string;
  runtime_provider: string;
  runtime_mode: string;
  environment: string;
};

function formatWorkflowMode(workflowMode: string): string {
  if (workflowMode === "foundry_hosted") {
    return "Foundry hosted";
  }
  return "LangGraph";
}

export default function App() {
  const hasAutoSelectedInitialRun = useRef(false);
  const hasUserInteractedWithRunSelection = useRef(false);
  const selectedThreadIdRef = useRef<string | null>(null);
  const selectionVersionRef = useRef(0);
  const [apiBase] = useState(() => getInitialApiBase());
  const [runtimeHealth, setRuntimeHealth] = useState<RuntimeHealth | null>(null);
  const [runtimeHealthError, setRuntimeHealthError] = useState<string | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [activeHistoryThreadId, setActiveHistoryThreadId] = useState<string | null>(
    null,
  );
  const [isComposingNewRun, setIsComposingNewRun] = useState(false);
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRunListItem[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalRuns, setTotalRuns] = useState(0);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [selectedWorkflowDetails, setSelectedWorkflowDetails] =
    useState<WorkflowRunDetails | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>(
    [],
  );
  const [latestOutput, setLatestOutput] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [statusFilter, setStatusFilter] = useState<"all" | WorkflowStatus>(
    "all",
  );
  const [searchTerm, setSearchTerm] = useState("");
  const [isStartingWorkflow, setIsStartingWorkflow] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);
  const [isRichStreamConnected, setIsRichStreamConnected] = useState(false);
  const [richEnvelopeCount, setRichEnvelopeCount] = useState(0);

  const clearSelectedRunPanels = useCallback(() => {
    setSelectedWorkflowDetails(null);
    setEvents([]);
    setPendingApprovals([]);
    setLatestOutput(null);
    setActionError(null);
    setDetailsError(null);
  }, []);

  const loadRuntimeHealth = useCallback(
    async (baseUrl: string, signal?: AbortSignal) => {
      setRuntimeHealthError(null);
      setRuntimeHealth(null);
      try {
        const payload = await fetchApiJson<RuntimeHealth>(baseUrl, "/api/health", {
          signal,
        });
        setRuntimeHealth(payload);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (!signal?.aborted) {
          setRuntimeHealthError(
            error instanceof Error
              ? error.message
              : "Unable to reach backend health endpoint",
          );
        }
      }
    },
    [],
  );
  const loadWorkflowHistory = useCallback(
    async (page: number) => {
      setIsHistoryLoading(true);
      setHistoryError(null);
      try {
        const params = new URLSearchParams({
          page: String(page),
          page_size: String(pageSize),
        });
        if (statusFilter !== "all") {
          params.set("status", statusFilter);
        }
        const data = await fetchApiJson<WorkflowRunListResponse>(
          apiBase,
          `/api/workflows?${params.toString()}`,
        );
        setWorkflowRuns(data.items);
        setTotalRuns(data.total);
        if (typeof data.page_size === "number" && data.page_size > 0) {
          setPageSize(data.page_size);
        }

        if (
          !hasAutoSelectedInitialRun.current &&
          !hasUserInteractedWithRunSelection.current
        ) {
          hasAutoSelectedInitialRun.current = true;
          if (!selectedThreadIdRef.current && data.items.length > 0) {
            selectionVersionRef.current += 1;
            selectedThreadIdRef.current = data.items[0].thread_id;
            setActiveHistoryThreadId(data.items[0].thread_id);
            setSelectedThreadId(data.items[0].thread_id);
          }
        }
      } catch (error) {
        setHistoryError(
          error instanceof Error ? error.message : "Unexpected history error",
        );
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [apiBase, pageSize, statusFilter],
  );

  const loadWorkflowDetails = useCallback(
    async (
      threadId: string,
      expectedSelectionVersion = selectionVersionRef.current,
    ) => {
      setIsDetailsLoading(true);
      setDetailsError(null);
      try {
        const details = redactWorkflowRunDetails(
          await fetchApiJson<WorkflowRunDetails>(
            apiBase,
            `/api/workflows/${encodeURIComponent(threadId)}`,
          ),
        );
        if (
          selectedThreadIdRef.current !== threadId ||
          selectionVersionRef.current !== expectedSelectionVersion
        ) {
          return;
        }
        setSelectedWorkflowDetails(details);
        setEvents(details.events ?? []);
        setPendingApprovals(details.pending_approvals ?? []);
        setLatestOutput(details.latest_output ?? null);
      } catch (error) {
        if (
          selectedThreadIdRef.current === threadId &&
          selectionVersionRef.current === expectedSelectionVersion
        ) {
          setDetailsError(
            error instanceof Error
              ? error.message
              : "Unexpected workflow details error",
          );
        }
      } finally {
        if (selectionVersionRef.current === expectedSelectionVersion) {
          setIsDetailsLoading(false);
        }
      }
    },
    [apiBase],
  );

  useEffect(() => {
    void loadWorkflowHistory(currentPage);
  }, [currentPage, loadWorkflowHistory]);

  useEffect(() => {
    const controller = new AbortController();
    void loadRuntimeHealth(apiBase, controller.signal);
    return () => controller.abort();
  }, [apiBase, loadRuntimeHealth]);

  useEffect(() => {
    if (isComposingNewRun || !selectedThreadId) {
      return;
    }
    void loadWorkflowDetails(selectedThreadId, selectionVersionRef.current);
  }, [isComposingNewRun, selectedThreadId, loadWorkflowDetails]);

  useEffect(() => {
    if (isComposingNewRun || !selectedThreadId) {
      return;
    }
    if (
      selectedWorkflowDetails &&
      !["running", "waiting_approval"].includes(selectedWorkflowDetails.status)
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadWorkflowDetails(selectedThreadId, selectionVersionRef.current);
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [
    isComposingNewRun,
    selectedThreadId,
    selectedWorkflowDetails,
    loadWorkflowDetails,
  ]);

  useEffect(() => {
    if (isComposingNewRun || !selectedThreadId) {
      setIsRichStreamConnected(false);
      setRichEnvelopeCount(0);
      return;
    }

    setRichEnvelopeCount(0);
    const source = openRichThreadStream(
      apiBase,
      selectedThreadId,
      (envelope) => {
        const nativeEvent = redactWorkflowEvent(envelope.native_event);
        if (selectedThreadIdRef.current !== nativeEvent.thread_id) {
          return;
        }

        setEvents((previous) => {
          if (previous.some((event) => event.id === nativeEvent.id)) {
            return previous;
          }
          return [...previous, nativeEvent];
        });
        setRichEnvelopeCount((count) => count + 1);

        if (
          nativeEvent.type === "workflow.output" ||
          nativeEvent.type === "hitl.request" ||
          nativeEvent.type === "hitl.response" ||
          nativeEvent.type === "checkpoint.created"
        ) {
          void loadWorkflowDetails(
            nativeEvent.thread_id,
            selectionVersionRef.current,
          );
          void loadWorkflowHistory(currentPage);
        }
      },
    );

    setIsRichStreamConnected(true);
    source.onerror = () => {
      setIsRichStreamConnected(false);
    };

    return () => {
      setIsRichStreamConnected(false);
      setRichEnvelopeCount(0);
      source.close();
    };
  }, [
    apiBase,
    currentPage,
    isComposingNewRun,
    loadWorkflowDetails,
    loadWorkflowHistory,
    selectedThreadId,
  ]);

  const filteredRuns = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) {
      return workflowRuns;
    }
    return workflowRuns.filter((run) => {
      return (
        run.thread_id.toLowerCase().includes(query) ||
        run.input_summary.toLowerCase().includes(query)
      );
    });
  }, [workflowRuns, searchTerm]);

  const refreshAll = useCallback(async () => {
    await loadWorkflowHistory(currentPage);
    if (!isComposingNewRun && selectedThreadId) {
      await loadWorkflowDetails(selectedThreadId, selectionVersionRef.current);
    }
    await loadRuntimeHealth(apiBase);
  }, [
    apiBase,
    currentPage,
    isComposingNewRun,
    loadWorkflowDetails,
    loadWorkflowHistory,
    loadRuntimeHealth,
    selectedThreadId,
  ]);

  const startWorkflow = useCallback(async () => {
    if (!message.trim()) {
      return;
    }

    hasUserInteractedWithRunSelection.current = true;
    const selectionVersion = selectionVersionRef.current + 1;
    selectionVersionRef.current = selectionVersion;
    setIsStartingWorkflow(true);
    try {
      const payload = await fetchApiJson<{ thread_id: string }>(
        apiBase,
        "/api/chat/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        },
      );
      if (selectionVersionRef.current !== selectionVersion) {
        return;
      }
      setCurrentPage(1);
      clearSelectedRunPanels();
      selectedThreadIdRef.current = payload.thread_id;
      setActiveHistoryThreadId(payload.thread_id);
      setIsComposingNewRun(false);
      setSelectedThreadId(payload.thread_id);
      await loadWorkflowHistory(1);
      await loadWorkflowDetails(payload.thread_id, selectionVersion);
    } finally {
      setIsStartingWorkflow(false);
    }
  }, [apiBase, clearSelectedRunPanels, loadWorkflowDetails, loadWorkflowHistory, message]);

  const submitHitlDecision = useCallback(
    async (
      approval: PendingApproval,
      decision: "approve" | "reject",
      comment: string,
    ) => {
      setIsActionLoading(true);
      setActionError(null);
      try {
        try {
          await fetchApiJson<unknown>(
            apiBase,
            "/api/hitl/respond",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                checkpoint_id: approval.checkpoint_id,
                decision,
                reviewer: "demo-user",
                comments: comment,
              }),
            },
            { allowNoContent: true },
          );
        } catch (error) {
          setActionError(
            error instanceof Error
              ? error.message
              : "Unable to submit HITL decision",
          );
          return;
        }

        if (selectedThreadId) {
          await loadWorkflowDetails(selectedThreadId, selectionVersionRef.current);
        }
        await loadWorkflowHistory(currentPage);
      } finally {
        setIsActionLoading(false);
      }
    },
    [apiBase, currentPage, loadWorkflowDetails, loadWorkflowHistory, selectedThreadId],
  );

  const selectWorkflow = (threadId: string) => {
    hasUserInteractedWithRunSelection.current = true;
    clearSelectedRunPanels();
    selectionVersionRef.current += 1;
    selectedThreadIdRef.current = threadId;
    setActiveHistoryThreadId(threadId);
    setIsComposingNewRun(false);
    setSelectedThreadId(threadId);
  };

  const openWorkflow = useCallback(
    async (threadId: string) => {
      hasUserInteractedWithRunSelection.current = true;
      clearSelectedRunPanels();
      const selectionVersion = selectionVersionRef.current + 1;
      selectionVersionRef.current = selectionVersion;
      selectedThreadIdRef.current = threadId;
      setActiveHistoryThreadId(threadId);
      setIsComposingNewRun(false);
      setSelectedThreadId(threadId);
      await loadWorkflowHistory(1);
      await loadWorkflowDetails(threadId, selectionVersion);
    },
    [clearSelectedRunPanels, loadWorkflowDetails, loadWorkflowHistory],
  );

  const handleNewRun = () => {
    hasUserInteractedWithRunSelection.current = true;
    selectionVersionRef.current += 1;
    selectedThreadIdRef.current = null;
    flushSync(() => {
      setActiveHistoryThreadId(null);
      setIsComposingNewRun(true);
      setSelectedThreadId(null);
      clearSelectedRunPanels();
      setMessage(DEFAULT_MESSAGE);
    });
  };

  const totalPages = Math.max(1, Math.ceil(totalRuns / pageSize));
  const visibleSelectedThreadId = isComposingNewRun ? null : selectedThreadId;
  const visibleActiveHistoryThreadId = isComposingNewRun
    ? null
    : activeHistoryThreadId;
  const selectedThreadAssistantContext = useMemo(
    () =>
      createSafeSelectedThreadContext({
        threadId: visibleSelectedThreadId,
        details: selectedWorkflowDetails,
        events,
        approvals: pendingApprovals,
      }),
    [
      events,
      pendingApprovals,
      selectedWorkflowDetails,
      visibleSelectedThreadId,
    ],
  );

  useAgentContext({
    description:
      "Safe metadata for the selected order-resolution workflow thread. It contains only the thread ID, normalized status, event types and timestamps, pending approval count, and whether output is available.",
    value: selectedThreadAssistantContext,
  });
  const runtimeBadgeLabel = runtimeHealth
    ? `${runtimeHealth.environment} • ${formatWorkflowMode(runtimeHealth.workflow_mode)} • ${runtimeHealth.runtime_provider}/${runtimeHealth.runtime_mode}`
    : runtimeHealthError
      ? "Backend unavailable"
      : "Checking backend health...";

  return (
    <AppShell
      onNewRun={handleNewRun}
      onRefresh={() => void refreshAll()}
      runtimeBadgeLabel={runtimeBadgeLabel}
      runtimeHealthError={runtimeHealthError}
    >
      <WorkflowHistorySidebar
        runs={filteredRuns}
        selectedThreadId={visibleActiveHistoryThreadId}
        statusFilter={statusFilter}
        searchTerm={searchTerm}
        page={currentPage}
        pageSize={pageSize}
        total={totalRuns}
        isLoading={isHistoryLoading}
        error={historyError}
        onSelect={selectWorkflow}
        onStatusFilterChange={(value) => {
          setStatusFilter(value);
          setCurrentPage(1);
        }}
        onSearchChange={setSearchTerm}
        onPreviousPage={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
        onNextPage={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
      />

      <section className="center-column">
        <WorkflowRunComposer
          message={message}
          isSubmitting={isStartingWorkflow}
          onMessageChange={setMessage}
          onSubmit={startWorkflow}
          onClear={() => setMessage("")}
        />
        <ManualTestPanel
          apiBase={apiBase}
          onLoadPrompt={setMessage}
          onOpenWorkflow={openWorkflow}
        />
        <WorkflowTimeline
          events={events}
          hasSelectedWorkflow={Boolean(visibleSelectedThreadId)}
          isLoading={isDetailsLoading}
          error={detailsError}
          isLiveStreaming={isRichStreamConnected}
          richEnvelopeCount={richEnvelopeCount}
          onRefresh={async () => {
            if (visibleSelectedThreadId) {
              await loadWorkflowDetails(
                visibleSelectedThreadId,
                selectionVersionRef.current,
              );
            }
          }}
        />
        <AgUiThreadPanel apiBase={apiBase} threadId={visibleSelectedThreadId} />
      </section>

      <section className="right-column">
        <HumanApprovalPanel
          approvals={pendingApprovals}
          events={events}
          isSubmitting={isActionLoading}
          error={actionError}
          onDecision={submitHitlDecision}
        />
        <LatestOutputPanel
          output={latestOutput}
          status={selectedWorkflowDetails?.status ?? null}
        />
        <RagEvidencePanel details={selectedWorkflowDetails} events={events} />
        <RunMetadataPanel
          metadata={selectedWorkflowDetails?.metadata ?? null}
        />
        <SelectedThreadAssistantPanel
          apiBase={apiBase}
          threadId={visibleSelectedThreadId}
        />
      </section>
    </AppShell>
  );
}
