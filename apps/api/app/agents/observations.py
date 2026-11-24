"""Compact search observations. Snippets are not verified claims."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence.store import record_evidence, stable_id
from app.models.entities import Claim, EvidenceSource
from app.schemas.contracts import Source

SNIPPET_CHARS = 160
TITLE_CHARS = 120
MAX_CONTEXT_SOURCES = 8
STATEMENT_CHARS = 240
PROCESSED_STATUSES = frozenset({"extracted", "irrelevant", "extraction_failed", "inaccessible", "rejected"})


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def _useful(title: str, snippet: str, url: str) -> bool:
    if snippet.strip():
        return True
    cleaned = title.strip()
    if not cleaned or cleaned.startswith("http"):
        return False
    return cleaned.rstrip("/") != url.rstrip("/")


def search_progress_fa(total: int, new_useful: int, thin: int) -> str:
    return (
        f"جست‌وجو انجام شد: {total} نتیجه، {new_useful} منبع تازه قابل بررسی، "
        f"{thin} نتیجه بدون متن. این هنوز شاهد تأییدشده نیست."
    )


def page_progress_fa(claim_count: int, *, status: str = "") -> tuple[str, str]:
    if status == "extraction_failed":
        return "صفحه دریافت شد اما استخراج یا اعتبارسنجی ناموفق بود.", "research.extraction_failed"
    if status == "inaccessible":
        return "صفحه در دسترس نبود.", "research.source_inaccessible"
    if status == "irrelevant":
        return (
            "صفحه دریافت شد اما ردیف یا جمله مرتبط با محصول، کد HS، سال یا اصطلاح تجاری استخراج نشد.",
            "research.page_irrelevant",
        )
    if status == "rejected":
        return (
            "متن مرتبط دیده شد اما اعتبارسنجی آن را به عنوان شاهد نپذیرفت. عددی ساخته نشد.",
            "research.page_rejected",
        )
    if status == "already_processed":
        return (
            "این منبع قبلاً بررسی شده است. استخراج دوباره انجام نشد.",
            "research.source_already_processed",
        )
    if claim_count > 0:
        return (
            f"صفحه خوانده شد و {claim_count} ادعا ذخیره شد. این شاهد قابل استناد است.",
            "market.evidence_ready",
        )
    return (
        "صفحه خوانده شد اما ادعای قابل اتکا استخراج نشد. شاهد تأییدشده اضافه نشد.",
        "research.page_read",
    )


def absorb_search_results(
    state: dict,
    results: list,
    *,
    run_id: str,
    db: Session | None = None,
) -> dict:
    """Store each new URL once. Returns counts; does not create claims."""

    observations = list(state.get("observations") or [])
    known = {str(item.get("url_key") or ""): item for item in observations}
    added: list[dict] = []
    thin = 0
    total = 0
    new_useful = 0
    for item in results or []:
        if not isinstance(item, dict):
            continue
        url = normalize_url(str(item.get("url") or ""))
        if not url:
            continue
        total += 1
        title = str(item.get("title") or "").strip()[:TITLE_CHARS]
        snippet = str(item.get("snippet") or "").strip()[:SNIPPET_CHARS]
        useful = _useful(title, snippet, url)
        if not useful:
            thin += 1
        current = known.get(url)
        if current is not None:
            became_useful = useful and not current.get("useful")
            if snippet and not current.get("snippet"):
                current["snippet"] = snippet
            if title and not str(current.get("title") or "").strip():
                current["title"] = title
            if useful:
                current["useful"] = True
            if became_useful:
                new_useful += 1
            continue
        obs_id = stable_id("ev", run_id or "", url, "", "", "")
        row = {
            "id": obs_id,
            "url": url,
            "url_key": url,
            "title": title,
            "snippet": snippet,
            "status": "unread",
            "useful": useful,
            "claim_count": 0,
        }
        if db is not None:
            published = item.get("published_period")
            stored_row = record_evidence(
                db,
                run_id=run_id,
                source=Source(
                    url=url,
                    title=(title or url)[:512],
                    publisher=str(item.get("publisher") or "")[:256],
                    published_at=published if isinstance(published, str) else None,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    provider=str(item.get("provider") or "web")[:64],
                    reliability_note="obs:unread",
                ),
                excerpt=snippet or None,
            )
            row["id"] = stored_row.id
        observations.append(row)
        known[url] = row
        added.append(row)
        urls = state.setdefault("urls", [])
        if url not in urls:
            urls.append(url)
        if useful:
            new_useful += 1
    state["observations"] = observations
    return {
        "total": total,
        "new_useful": new_useful,
        "thin": thin,
        "added": added,
    }


def processed_source(state: dict, url: str) -> dict | None:
    key = normalize_url(url)
    if not key:
        return None
    for row in state.get("observations") or []:
        if row.get("url_key") == key or normalize_url(str(row.get("url") or "")) == key:
            if str(row.get("status") or "") in PROCESSED_STATUSES:
                return row
    return None


def page_read_status(*, stored: int, raw_claims: int, extract_outcome: str) -> str:
    if stored > 0:
        return "extracted"
    if raw_claims > 0 or extract_outcome == "rejected":
        return "rejected"
    return "irrelevant" if extract_outcome == "irrelevant" else "extraction_failed"


def mark_pages(
    state: dict,
    urls: list[str],
    *,
    status: str,
    claim_count: int,
    excerpt: str = "",
    db: Session | None = None,
) -> None:
    keys = {normalize_url(url) for url in urls if normalize_url(url)}
    if not keys:
        return
    rank = {"unread": 0, "inaccessible": 1, "fetched": 2, "irrelevant": 3,
            "rejected": 3, "extraction_failed": 3, "extracted": 4}
    snippet = " ".join((excerpt or "").split())[:SNIPPET_CHARS]
    for row in state.get("observations") or []:
        if row.get("url_key") not in keys and row.get("url") not in keys:
            continue
        current = str(row.get("status") or "unread")
        if rank.get(status, 0) >= rank.get(current, 0):
            row["status"] = status
        row["claim_count"] = max(int(row.get("claim_count") or 0), claim_count)
        if snippet and not row.get("snippet"):
            row["snippet"] = snippet
        if db is not None and row.get("id"):
            existing = db.get(EvidenceSource, row["id"])
            if existing is not None:
                existing.reliability_note = f"obs:{row['status']}"
                if snippet and not existing.raw_excerpt:
                    existing.raw_excerpt = snippet
                db.commit()


def load_observations(db: Session, run_id: str) -> list[dict]:
    sources = list(
        db.scalars(select(EvidenceSource).where(EvidenceSource.run_id == run_id)).all()
    )
    claims = list(
        db.scalars(select(Claim).where(Claim.run_id == run_id, Claim.status == "active")).all()
    )
    by_url: dict[str, int] = {}
    for claim in claims:
        key = normalize_url(str(claim.source_url or ""))
        if key:
            by_url[key] = by_url.get(key, 0) + 1
    rows: list[dict] = []
    for source in sources:
        note = source.reliability_note or ""
        if not note.startswith("obs:"):
            continue
        status = note.split(":", 1)[1]
        if status == "rejected":
            status = "extraction_failed"
        if status not in PROCESSED_STATUSES | {"unread", "fetched"}:
            status = "unread"
        url = normalize_url(source.url) or source.url
        claim_count = by_url.get(url, 0)
        if claim_count:
            status = "extracted"
        rows.append(
            {
                "id": source.id,
                "url": url,
                "url_key": url,
                "title": (source.title or "")[:TITLE_CHARS],
                "snippet": (source.raw_excerpt or "")[:SNIPPET_CHARS],
                "status": status,
                "useful": _useful(source.title or "", source.raw_excerpt or "", url),
                "claim_count": claim_count,
            }
        )
    return rows


def context_sources(observations: list[dict] | None) -> list[dict]:
    rows = list(observations or [])
    unread = [row for row in rows if row.get("status") == "unread"]
    later = [row for row in rows if row.get("status") != "unread"]
    picked = unread[-(MAX_CONTEXT_SOURCES - 2):] + later[-2:]
    compact = []
    for row in picked:
        status = str(row.get("status") or "unread")
        snippet_limit = SNIPPET_CHARS if status == "unread" else 0
        compact.append(
            {
                "id": row.get("id"),
                "status": status,
                "url": row.get("url"),
                "title": str(row.get("title") or "")[:TITLE_CHARS],
                "snippet": str(row.get("snippet") or "")[:snippet_limit],
                "useful": bool(row.get("useful")),
                "claim_count": int(row.get("claim_count") or 0),
            }
        )
    return compact


def research_counts(observations: list[dict] | None, evidence_rows: list[dict]) -> dict[str, int]:
    counts = {
        "unread": 0,
        "fetched": 0,
        "extracted": 0,
        "irrelevant": 0,
        "extraction_failed": 0,
        "inaccessible": 0,
        "verified_claims": len(evidence_rows),
    }
    for row in observations or []:
        status = str(row.get("status") or "")
        if status == "rejected":
            status = "extraction_failed"
        if status in counts:
            counts[status] += 1
    counts["processed"] = sum(counts.get(status, 0) for status in PROCESSED_STATUSES)
    return counts


def compact_evidence(index: dict) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for row in index.values():
        if not isinstance(row, dict):
            continue
        key = str(row.get("claim_id") or row.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({**row, "id": key})
    return rows


def observation_sources(observations: list[dict] | None, *, limit: int | None = 12) -> list[Source]:
    sources: list[Source] = []
    for row in list(observations or [])[:limit]:
        url = str(row.get("url") or "")
        if not url:
            continue
        sources.append(
            Source(
                url=url,
                title=str(row.get("title") or url)[:512],
                publisher="web",
                fetched_at="",
                provider="free_web",
                reliability_note=f"obs:{row.get('status') or 'unread'}",
            )
        )
    return sources


def evidence_context(rows: list[dict], seen: set[str], selection: dict) -> list[dict]:
    """Preview new evidence and let the model page through the entire claim ledger."""
    if selection:
        requested = selection.get("ids")
        ids = set(map(str, requested[:12])) if isinstance(requested, list) else set()
        country = str(selection.get("country") or "").upper()
        try:
            offset = max(0, int(selection.get("offset") or 0))
        except (ValueError, TypeError):
            offset = 0
        matching = [row for row in rows if (not ids or row["id"] in ids) and (not country or row["country"] == country)]
        selected = matching[offset:offset + 12]
    else:
        recent = [row for row in rows if row["id"] not in seen]
        known = [row for row in reversed(rows) if row["id"] in seen]
        selected = (recent + known[:4])[:12]
    compact = []
    for row in selected:
        item = {
            key: row[key]
            for key in ("id", "claim_id", "country", "hs_scope", "period", "source_id")
            if row.get(key)
        }
        if selection or row["id"] not in seen:
            statement = str(row["statement"])
            if trade := row.get("trade"):
                item["trade"] = trade
                if not selection:
                    statement = re.sub(r"\s+\(https?://[^\s()]+\)", "", statement)
            item["statement"] = statement[:500 if selection else STATEMENT_CHARS]
        if selection:
            item["source_url"] = row.get("source_url")
        compact.append(item)
    return compact


def evidence_coverage(rows: list[dict], candidates: dict) -> dict:
    coverage: dict = {}
    for row in rows:
        country = row.get("country") or "unmapped"
        bucket = coverage.setdefault(country, {"claim_count": 0, "criteria": {}})
        bucket["claim_count"] += 1
    for country, proposal in candidates.items():
        bucket = coverage.setdefault(country, {"claim_count": 0, "criteria": {}})
        bucket["criteria"] = {
            item["criterion"]: len(item["evidence_ids"])
            for item in proposal.get("criteria") or []
        }
    return coverage
