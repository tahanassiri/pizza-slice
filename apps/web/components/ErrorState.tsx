import { fa } from "@/lib/i18n/fa";

export function ErrorState({
  title = fa.error.title,
  message = fa.error.generic,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="nova-panel flex flex-col items-start gap-3 p-6" role="alert">
      <p className="text-lg font-semibold text-[var(--danger)]">{title}</p>
      <p className="text-sm text-ink-muted">{message}</p>
      {onRetry ? (
        <button type="button" className="nova-btn-primary" onClick={onRetry}>
          {fa.error.retry}
        </button>
      ) : null}
    </div>
  );
}
