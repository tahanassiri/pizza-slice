import { fa } from "@/lib/i18n/fa";

export function MockBanner({
  preview = false,
  className = "",
}: {
  preview?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`mock-banner no-print rounded-xl px-3 py-2 text-sm font-medium ${className}`}
      role="status"
    >
      {preview ? fa.mockPreviewBadge : fa.mockBadge}
      <span className="mx-2 opacity-40">·</span>
      <span className="font-normal opacity-90">{fa.mockNotice}</span>
    </div>
  );
}
