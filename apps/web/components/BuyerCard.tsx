import { fa } from "@/lib/i18n/fa";
import type { Buyer } from "@/types";
import { SourceBadge } from "./SourceBadge";

const verifyTone: Record<Buyer["verification_status"], string> = {
  unverified: "bg-fog text-ink-muted",
  source_backed: "bg-[var(--ok-soft)] text-[var(--ok)]",
  needs_review: "bg-[var(--warn-soft)] text-[var(--warn)]",
  rejected: "bg-[var(--danger-soft)] text-[var(--danger)]",
};

export function BuyerCard({ buyer }: { buyer: Buyer }) {
  return (
    <article className="nova-panel p-4">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-ink">{buyer.company_name}</h3>
          {buyer.business_type ? (
            <p className="text-sm text-ink-muted">{buyer.business_type}</p>
          ) : null}
        </div>
        <span
          className={`rounded-lg px-2 py-1 text-xs font-semibold ${verifyTone[buyer.verification_status]}`}
        >
          {fa.verification[buyer.verification_status]}
        </span>
      </div>

      {buyer.fit_evidence.length ? (
        <div className="mb-3">
          <p className="mb-1 text-xs font-medium text-ink-soft">{fa.buyers.fit}</p>
          <ul className="list-disc space-y-1 pr-5 text-sm text-ink-muted">
            {buyer.fit_evidence.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3 text-sm">
        {buyer.website ? (
          <a
            href={buyer.website}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
            dir="ltr"
          >
            {fa.buyers.website}
          </a>
        ) : null}
        {buyer.contact?.email || buyer.contact?.phone ? (
          <span className="text-ink-muted">
            {fa.buyers.contact}:{" "}
            <span dir="ltr">
              {buyer.contact.email || buyer.contact.phone}
            </span>
            {buyer.contact.note_fa ? ` — ${buyer.contact.note_fa}` : ""}
          </span>
        ) : null}
      </div>

      {buyer.sources.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {buyer.sources.map((s) => (
            <SourceBadge key={s.url} source={s} />
          ))}
        </div>
      ) : null}
    </article>
  );
}
