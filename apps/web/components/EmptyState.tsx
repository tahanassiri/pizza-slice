import type { ReactNode } from "react";
import { fa } from "@/lib/i18n/fa";

export function EmptyState({
  title = fa.empty.title,
  hint,
  action,
}: {
  title?: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--study-line)] bg-white/80 p-6">
      <p className="text-lg font-semibold text-[var(--study-ink)]">{title}</p>
      {hint ? <p className="mt-1 text-sm text-[var(--study-muted)]">{hint}</p> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
