import type { Source } from "@/types";

export function SourceBadge({ source }: { source: Source }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex max-w-full items-center gap-1 truncate rounded-lg border border-line bg-white px-2 py-1 text-xs text-ink-soft hover:border-accent hover:text-accent"
      title={`${source.title} — ${source.reliability_note}`}
    >
      <span className="truncate">{source.publisher}</span>
      <span className="opacity-50">·</span>
      <span className="truncate opacity-80">{source.provider}</span>
    </a>
  );
}
