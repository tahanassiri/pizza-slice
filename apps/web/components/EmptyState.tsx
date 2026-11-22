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
    <div className="nova-panel flex flex-col items-start gap-2 p-6">
      <p className="text-lg font-semibold text-ink-soft">{title}</p>
      {hint ? <p className="text-sm text-ink-muted">{hint}</p> : null}
      {action}
    </div>
  );
}
