"""Buyer research after human market gate — verify, never invent companies."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.agents.tool_contracts import ToolCall
from app.models.entities import CompanyProfile
from app.schemas.contracts import Buyer, BuyerContact, Source
from app.tools.executor import ToolExecutor
from app.tools.verify_company import verify_company

CATEGORY_FA = {
    "importer": "واردکننده",
    "distributor": "توزیع‌کننده",
    "wholesaler": "عمده‌فروش",
    "industrial_end_user": "مصرف‌کننده صنعتی",
    "seller": "فروشنده",
    "directory": "فهرست",
    "unknown": "نقش نامشخص",
}

ROLE_QUERIES = (
    ("importer", "{product} importer {country}"),
    ("distributor", "{product} distributor {country}"),
    ("wholesaler", "{product} wholesaler {country}"),
    ("industrial_end_user", "{product} industrial buyer {country}"),
)

_SKIP_HOSTS = (
    "wikipedia.org",
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "yahoo.com",
)

# Map verify statuses onto FE contract
_STATUS_MAP = {
    "candidate": "unverified",
    "source_backed": "source_backed",
    "needs_review": "needs_review",
    "rejected": "rejected",
}


def _domain(url: str | None) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().removeprefix("www.")


def candidates_from_search_hits(results: list[dict], *, country: str, product: str, role: str) -> list:
    """Companies only from source URLs. Names come from the result title, never invented contacts."""

    from app.schemas.contracts import Buyer, Source

    found = []
    for item in results:
        url = str(item.get("url") or "")
        if not url.startswith("http"):
            continue
        host = _domain(url)
        if not host or any(host.endswith(skip) or skip in host for skip in _SKIP_HOSTS):
            continue
        title = str(item.get("title") or "").strip()
        name = title.split(" - ")[0].split("|")[0].strip()[:180]
        if len(name) < 2:
            continue
        snippet = str(item.get("snippet") or item.get("reliability_note") or "")
        source = Source(
            url=url,
            title=title or url,
            publisher=str(item.get("publisher") or host),
            fetched_at=str(item.get("fetched_at") or ""),
            provider=str(item.get("provider") or "free_web"),
            reliability_note="نتیجه جست‌وجو — نقش هنوز تأیید نشده",
        )
        buyer = Buyer(
            company_name=name,
            website=url,
            country=country,
            business_type=CATEGORY_FA.get(role, CATEGORY_FA["unknown"]),
            fit_evidence=[snippet[:300]] if snippet else [f"منبع: {url}"],
            contact=None,
            verification_status="unverified",
            sources=[source],
        )
        found.append(buyer)
    return found


def collect_buyer_hits(executor: ToolExecutor | None, *, product: str, country_code: str) -> tuple[list, list]:
    """Role queries are a fixed tool checklist, not a model decision."""

    if executor is None:
        return [], []
    buyers = []
    sources = []
    for role, template in ROLE_QUERIES:
        result = executor.execute(
            ToolCall(
                tool="search_web",
                args={
                    "query": template.format(product=product, country=country_code),
                    "country": country_code,
                    "max_results": 4,
                },
            )
        )
        hits = (result.data or {}).get("results") or []
        parsed = candidates_from_search_hits(hits, country=country_code, product=product, role=role)
        buyers.extend(parsed)
        for buyer in parsed:
            sources.extend(buyer.sources)
    return buyers, sources


def discover_and_verify_buyers(
    db: Session,
    *,
    run_id: str,
    product: str,
    country_code: str,
    search_provider: object,
    executor: ToolExecutor | None = None,
    max_publish: int = 10,
) -> tuple[list[Buyer], list[Source], str, str | None, str | None]:
    """Returns buyers, sources, status, error_code, error_message_fa."""

    # Discovery goes through allowlisted web tools. Wiki search_buyers is not a candidate source.
    del search_provider
    try:
        raw_buyers, sources = collect_buyer_hits(
            executor, product=product, country_code=country_code
        )
    except Exception as exc:
        return (
            [],
            [],
            "failed",
            "PROVIDER_UNAVAILABLE",
            f"جست‌وجوی خریدار ناموفق ({type(exc).__name__}).",
        )
    sources = list(sources)
    if not raw_buyers:
        return (
            [],
            sources,
            "partial",
            "NO_BUYERS",
            "خریدار قابل استنادی از نتایج ابزار پیدا نشد.",
        )

    published: list[Buyer] = []
    seen_domains: set[str] = set()

    for cand in raw_buyers:
        domain = _domain(cand.website)
        if domain and domain in seen_domains:
            continue
        if domain:
            seen_domains.add(domain)

        # Prefer tool executor path (budgeted); fall back to direct verify
        if executor is not None:
            result = executor.execute(
                ToolCall(
                    tool="verify_company",
                    args={
                        "company_name": cand.company_name,
                        "website": cand.website,
                        "country": country_code,
                        "product": product,
                        "snippets": list(cand.fit_evidence or [])[:3],
                        "fetch": True,
                    },
                )
            )
            data = result.data or {}
        else:
            # In tests with stub/no network, skip live fetch
            result = verify_company(
                company_name=cand.company_name,
                website=cand.website,
                country=country_code,
                product=product,
                snippets=list(cand.fit_evidence or [])[:3],
                fetch=False,
            )
            data = result.data or {}

        status_raw = str(data.get("verification_status") or "needs_review")
        if status_raw == "rejected":
            # persist rejection profile, do not publish as buyer card
            if domain:
                _upsert_company(
                    db,
                    domain=domain,
                    name=str(data.get("company_name") or cand.company_name),
                    country=country_code,
                    category=str(data.get("category") or "unknown"),
                    verification_status="rejected",
                    website=cand.website,
                    run_id=run_id,
                    payload={"reason": data.get("reason_fa")},
                )
            continue

        fe_status = _STATUS_MAP.get(status_raw, "needs_review")
        category = str(data.get("category") or "unknown")
        business_type = str(
            data.get("business_type_fa") or CATEGORY_FA.get(category, CATEGORY_FA["unknown"])
        )
        fit = list(data.get("fit_evidence") or cand.fit_evidence or [])
        if data.get("reason_fa"):
            fit.append(str(data["reason_fa"]))

        buyer_sources = list(cand.sources or [])
        buyer = Buyer(
            company_name=str(data.get("company_name") or cand.company_name),
            website=cand.website,
            country=country_code,
            business_type=business_type,
            fit_evidence=fit[:6],
            contact=None,  # never invent contacts
            verification_status=fe_status,  # type: ignore[arg-type]
            sources=buyer_sources,
        )

        # Only auto-publish source_backed + needs_review (not rejected)
        if fe_status in {"source_backed", "needs_review", "unverified"}:
            published.append(buyer)
            if domain:
                _upsert_company(
                    db,
                    domain=domain,
                    name=buyer.company_name,
                    country=country_code,
                    category=category,
                    verification_status=status_raw,
                    website=cand.website,
                    run_id=run_id,
                    payload={"fit": fit[:3]},
                )

        if len(published) >= max_publish:
            break

    # Separate: FE shows all published; source_backed first
    published.sort(
        key=lambda b: 0 if b.verification_status == "source_backed" else 1
    )

    if not published:
        return (
            [],
            sources,
            "partial",
            "NO_BUYERS",
            "پس از اعتبارسنجی، خریدار قابل‌انتشار یافت نشد (آگهی فروش حذف شد).",
        )

    return published, sources, "completed", None, None


def _upsert_company(
    db: Session,
    *,
    domain: str,
    name: str,
    country: str,
    category: str,
    verification_status: str,
    website: str | None,
    run_id: str,
    payload: dict,
) -> None:
    from sqlalchemy import select

    row = db.scalar(
        select(CompanyProfile).where(
            CompanyProfile.canonical_domain == domain,
            CompanyProfile.country == country,
        )
    )
    now = datetime.now(timezone.utc)
    if row:
        row.company_name = name
        row.category = category
        row.verification_status = verification_status
        row.website = website
        row.payload_json = json.dumps(payload, ensure_ascii=False)
        row.last_checked = now
        row.origin_run_id = run_id
    else:
        db.add(
            CompanyProfile(
                id=f"co_{secrets.token_hex(8)}",
                canonical_domain=domain,
                company_name=name,
                country=country,
                category=category,
                verification_status=verification_status,
                website=website,
                payload_json=json.dumps(payload, ensure_ascii=False),
                last_checked=now,
                origin_run_id=run_id,
            )
        )
    db.commit()
