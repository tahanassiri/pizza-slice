import { fa } from "@/lib/i18n/fa";

export function ConnectionBanner({
  onRetry,
  onClear,
  checkingStatus = false,
}: {
  onRetry: () => void;
  onClear?: () => void;
  checkingStatus?: boolean;
}) {
  return (
    <div
      className="mb-4 overflow-hidden rounded-2xl border border-[var(--cockpit-danger)] bg-[linear-gradient(120deg,rgba(240,113,103,0.22),rgba(11,20,38,0.9))] px-4 py-4 shadow-[0_0_40px_rgba(240,113,103,0.18)]"
      role={checkingStatus ? "status" : "alert"}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mt-1 text-lg font-semibold text-white">{fa.cockpit.connectionLost}</p>
          <p className="mt-1 max-w-2xl text-sm text-[var(--cockpit-muted)]">
            {checkingStatus ? fa.cockpit.statusPolling : fa.cockpit.connectionLostHint}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-xl bg-[var(--cockpit-danger)] px-4 py-2 text-xs font-semibold text-white"
            onClick={onRetry}
          >
            {fa.analysis.reconnect}
          </button>
          {onClear ? (
            <button
              type="button"
              className="rounded-xl border border-[var(--cockpit-line)] px-4 py-2 text-xs text-[var(--cockpit-muted)]"
              onClick={onClear}
            >
              {fa.cockpit.clearDisconnect}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
