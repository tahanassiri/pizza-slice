import { fa } from "@/lib/i18n/fa";
import type { ConfidenceLevel } from "@/types";

const tone: Record<ConfidenceLevel, string> = {
  high: "text-[var(--ok)]",
  medium: "text-[var(--warn)]",
  low: "text-[var(--danger)]",
  unknown: "text-ink-muted",
};

export function ConfidenceLabel({ level }: { level: ConfidenceLevel }) {
  return (
    <span className={`text-xs font-semibold ${tone[level]}`}>
      {fa.confidence[level]}
    </span>
  );
}
