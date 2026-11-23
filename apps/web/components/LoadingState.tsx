import { fa } from "@/lib/i18n/fa";

export function LoadingState({
  label = fa.loading.pleaseWait,
  hint = fa.loading.hint,
}: {
  label?: string;
  hint?: string;
}) {
  return (
    <div
      className="nova-panel flex flex-col items-center gap-3 p-6 text-center sm:flex-row sm:items-center sm:text-right"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span
        className="inline-block h-6 w-6 shrink-0 rounded-full border-2 border-[var(--accent)]/30 border-t-[var(--accent)] animate-spin"
        aria-hidden
      />
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-semibold text-white">{label}</p>
        {hint ? (
          <p className="text-xs leading-5 text-[var(--ink-muted)]">{hint}</p>
        ) : null}
      </div>
    </div>
  );
}
