import { fa } from "@/lib/i18n/fa";
import type { Buyer } from "@/types";
import { SourceBadge } from "./SourceBadge";

const verifyTone: Record<Buyer["verification_status"], string> = {
  unverified: "bg-[#eef2f6] text-[var(--study-muted)]",
  source_backed: "bg-[var(--ok-soft)] text-[#027a48]",
  needs_review: "bg-[var(--warn-soft)] text-[#9a6700]",
  rejected: "bg-[var(--danger-soft)] text-[#b42318]",
};

export function BuyerCard({ buyer }: { buyer: Buyer }) {
  return (
    <article className="dossier-row overflow-hidden">
      <div className="flex items-stretch">
        <div
          className={`w-1.5 shrink-0 ${
            buyer.verification_status === "source_backed"
              ? "bg-[#0cb6aa]"
              : buyer.verification_status === "needs_review"
                ? "bg-[#e6b765]"
                : buyer.verification_status === "rejected"
                  ? "bg-[#f07167]"
                  : "bg-[#c5d3dc]"
          }`}
          aria-hidden
        />
        <div className="flex-1 p-4">
          <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-[0.65rem] uppercase tracking-[0.12em] text-[var(--study-muted)]">
                potential buyer
              </p>
              <h3 className="font-semibold text-[var(--study-ink)]">{buyer.company_name}</h3>
              {buyer.business_type ? (
                <p className="text-sm text-[var(--study-muted)]">{buyer.business_type}</p>
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
              <p className="mb-1 text-xs font-medium text-[var(--study-ink)]">{fa.buyers.fit}</p>
              <ul className="space-y-1 text-sm text-[var(--study-muted)]">
                {buyer.fit_evidence.map((e) => (
                  <li key={e}>• {e}</li>
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
                className="font-medium text-[#0cb6aa] hover:underline"
                dir="ltr"
              >
                {fa.buyers.website}
              </a>
            ) : null}
            {buyer.contact?.email || buyer.contact?.phone ? (
              <span className="text-[var(--study-muted)]">
                {fa.buyers.contact}:{" "}
                <span dir="ltr">{buyer.contact.email || buyer.contact.phone}</span>
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
        </div>
      </div>
    </article>
  );
}
