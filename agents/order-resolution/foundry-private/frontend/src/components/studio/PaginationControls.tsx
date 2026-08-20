type Props = {
  page: number;
  pageSize: number;
  total: number;
  visibleCount: number;
  isLoading: boolean;
  onPrevious: () => void;
  onNext: () => void;
};

export default function PaginationControls({
  page,
  pageSize,
  total,
  visibleCount,
  isLoading,
  onPrevious,
  onNext,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const canPrevious = page > 1 && !isLoading;
  const canNext = page < totalPages && !isLoading;

  return (
    <div className="pagination-controls">
      <button
        type="button"
        className="btn btn-secondary"
        disabled={!canPrevious}
        onClick={onPrevious}
      >
        Previous
      </button>
      <span className="muted">
        Page {page} of {totalPages} • {visibleCount} shown / {total} runs
      </span>
      <button
        type="button"
        className="btn btn-secondary"
        disabled={!canNext}
        onClick={onNext}
      >
        Next
      </button>
    </div>
  );
}
