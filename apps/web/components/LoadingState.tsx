import { fa } from "@/lib/i18n/fa";

export function LoadingState({ label = fa.loading.title }: { label?: string }) {
  return (
    <div className="nova-panel flex items-center gap-3 p-6" role="status" aria-live="polite">
      <span className="inline-block h-3 w-3 rounded-full bg-[var(--accent)] animate-pulse-soft" />
      <p className="text-sm text-[var(--ink-muted)]">{label}</p>
    </div>
  );
}
