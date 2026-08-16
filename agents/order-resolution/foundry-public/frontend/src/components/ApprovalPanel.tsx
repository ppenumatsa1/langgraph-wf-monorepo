type Props = {
  checkpointId: string | null;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
};

export default function ApprovalPanel({
  checkpointId,
  onApprove,
  onReject,
}: Props) {
  return (
    <section className="panel approval">
      <h2>Human-in-the-Loop</h2>
      {checkpointId ? (
        <>
          <p>
            Checkpoint pending: <strong>{checkpointId}</strong>
          </p>
          <div className="actions">
            <button className="btn approve" onClick={onApprove}>
              Approve
            </button>
            <button className="btn reject" onClick={onReject}>
              Reject
            </button>
          </div>
        </>
      ) : (
        <p className="muted">No pending approvals.</p>
      )}
    </section>
  );
}
