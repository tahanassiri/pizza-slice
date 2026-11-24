"""Compact search observations. Snippets are not verified claims."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence.store import record_evidence, stable_id
from app.models.entities import Claim, EvidenceSource
from app.schemas.contracts import Source

SNIPPET_CHARS = 160
TITLE_CHARS = 120
MAX_STORED = 24
MAX_CONTEXT_SOURCES = 8
STATEMENT_CHARS = 240


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
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


def page_progress_fa(claim_count: int) -> tuple[str, str]:
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
    state["observations"] = observations[-MAX_STORED:]
    return {
        "total": total,
        "new_useful": new_useful,
        "thin": thin,
        "added": added,
    }


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
    rank = {"unread": 0, "fetched": 1, "extracted": 2}
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
        if status not in {"unread", "fetched", "extracted"}:
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
    return rows[-MAX_STORED:]


def context_sources(observations: list[dict] | None) -> list[dict]:
    rows = list(observations or [])
    unread = [row for row in rows if row.get("status") == "unread"]
    later = [row for row in rows if row.get("status") != "unread"]
    picked = (unread[-MAX_CONTEXT_SOURCES:] + later[-4:])[:MAX_CONTEXT_SOURCES]
    compact = []
    for row in picked:
        compact.append(
            {
                "id": row.get("id"),
                "status": row.get("status") or "unread",
                "url": row.get("url"),
                "title": str(row.get("title") or "")[:TITLE_CHARS],
                "snippet": str(row.get("snippet") or "")[:SNIPPET_CHARS],
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
        "verified_claims": len(evidence_rows),
    }
    for row in observations or []:
        status = str(row.get("status") or "")
        if status in {"unread", "fetched", "extracted"}:
            counts[status] += 1
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
        item = dict(row)
        statement = str(item.get("statement") or "")
        if len(statement) > STATEMENT_CHARS:
            item["statement"] = statement[:STATEMENT_CHARS]
        rows.append(item)
    return rows[:12]


def observation_sources(observations: list[dict] | None) -> list[Source]:
    sources: list[Source] = []
    for row in list(observations or [])[:12]:
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
