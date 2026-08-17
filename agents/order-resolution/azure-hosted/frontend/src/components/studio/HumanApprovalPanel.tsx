import { useState } from "react";

import type { PendingApproval, WorkflowEvent } from "../../types/workflow";

type Props = {
  approvals: PendingApproval[];
  events: WorkflowEvent[];
  isSubmitting: boolean;
  error: string | null;
  onDecision: (
    approval: PendingApproval,
    decision: "approve" | "reject",
    comment: string,
  ) => Promise<void>;
};

export default function HumanApprovalPanel({
  approvals,
  events,
  isSubmitting,
  error,
  onDecision,
}: Props) {
  const [comment, setComment] = useState("Reviewed in UI");
  const pendingApproval = approvals.find(
    (approval) => approval.status === "pending",
  );
  const requestEvent = pendingApproval
    ? events
        .slice()
        .reverse()
        .find(
          (event) =>
            event.type === "hitl.request" &&
            event.payload.checkpoint_id === pendingApproval.checkpoint_id,
        )
    : null;
  const requestPayload = requestEvent?.payload ?? {};
  const action =
    pendingApproval?.action ??
    (typeof requestPayload.action === "string" ? requestPayload.action : null);
  const orderId =
    pendingApproval?.order_id ??
    (typeof requestPayload.order_id === "string" ? requestPayload.order_id : null);
  const amount =
    pendingApproval?.amount ??
    (typeof requestPayload.amount === "number" ? requestPayload.amount : null);

  return (
    <section className="panel panel-approval">
      <header className="panel-head">
        <h2>Human-in-the-Loop</h2>
      </header>

      {!pendingApproval ? (
        <p className="muted">No pending approvals.</p>
      ) : (
        <>
          {error ? <p className="error-text">{error}</p> : null}
          <p className="approval-question">
            {pendingApproval.question ?? "Approve the proposed action?"}
          </p>
          <dl className="approval-context">
            <div>
              <dt>Action</dt>
              <dd>{action ?? "n/a"}</dd>
            </div>
            <div>
              <dt>Order</dt>
              <dd>{orderId ?? "n/a"}</dd>
            </div>
            <div>
              <dt>Amount</dt>
              <dd>{amount ?? "n/a"}</dd>
            </div>
            <div>
              <dt>Checkpoint</dt>
              <dd>{pendingApproval.checkpoint_id}</dd>
            </div>
          </dl>

          <label className="comment-label" htmlFor="approval-comment">
            Comment
          </label>
          <textarea
            id="approval-comment"
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />

          <div className="approval-actions">
            <button
              type="button"
              className="btn btn-success"
              disabled={isSubmitting}
              onClick={() => onDecision(pendingApproval, "approve", comment)}
            >
              Approve
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={isSubmitting}
              onClick={() => onDecision(pendingApproval, "reject", comment)}
            >
              Reject
            </button>
          </div>
        </>
      )}
    </section>
  );
}
