import { fa } from "@/lib/i18n/fa";
import type { ConfidenceLevel } from "@/types";

const tone: Record<ConfidenceLevel, string> = {
  high: "text-[#027a48]",
  medium: "text-[#9a6700]",
  low: "text-[#b42318]",
  unknown: "text-[var(--study-muted)]",
};

export function ConfidenceLabel({ level }: { level: ConfidenceLevel }) {
  return (
    <span className={`text-xs font-semibold ${tone[level]}`}>
      {fa.confidence[level]}
    </span>
  );
}
