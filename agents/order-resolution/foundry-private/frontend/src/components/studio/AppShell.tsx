import type { ReactNode } from "react";

type Props = {
  onNewRun: () => void;
  onRefresh: () => void;
  runtimeBadgeLabel: string;
  runtimeHealthError: string | null;
  children: ReactNode;
};

export default function AppShell({
  onNewRun,
  onRefresh,
  runtimeBadgeLabel,
  runtimeHealthError,
  children,
}: Props) {
  return (
    <main className="studio-shell">
      <header className="studio-header">
        <div className="studio-header-title">
          <h1>LangGraph Order Resolution Studio</h1>
          <p>Run, observe, approve, and resume order-resolution workflows</p>
          <p className={runtimeHealthError ? "runtime-status runtime-error" : "runtime-status"}>
            Runtime: {runtimeBadgeLabel}
          </p>
        </div>
        <div className="header-right">
          <div className="header-actions">
            <button type="button" className="btn btn-primary" onClick={onNewRun}>
              New Run
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onRefresh}
            >
              Refresh
            </button>
          </div>
        </div>
      </header>
      <section className="studio-main">{children}</section>
    </main>
  );
}
