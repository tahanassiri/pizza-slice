"""Extract structured claims from untrusted page text — never execute instructions."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

import pycountry

from app.agents.hs_code import hs_codes_in_text
from app.agents.tool_contracts import ToolResult

# Strip common injection patterns from becoming "commands"
_INJECTION = re.compile(
    r"(ignore (all )?(previous|prior) instructions|system\s*:|you are now|"
    r"فرامین قبلی را نادیده|دستور سیستم)",
    re.I,
)
_TABLE = re.compile(r"<table\b[^>]*>(.*?)</table>", re.I | re.S)
_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
_CELL = re.compile(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_TRADE_WORD = re.compile(
    r"export|import|market|tariff|trade value|net ?weight|demand|production|"
    r"صادرات|واردات|بازار|تعرفه|تقاضا",
    re.I,
)
# Names that appear as table cells. A cell is mapped only when it equals one of these.
_COUNTRY_NAMES = {
    "afghanistan": "AF",
    "bahrain": "BH",
    "china": "CN",
    "france": "FR",
    "germany": "DE",
    "hong kong": "HK",
    "hong kong, china": "HK",
    "india": "IN",
    "iran": "IR",
    "iran, islamic rep.": "IR",
    "islamic republic of iran": "IR",
    "iraq": "IQ",
    "italy": "IT",
    "japan": "JP",
    "kuwait": "KW",
    "malaysia": "MY",
    "netherlands": "NL",
    "oman": "OM",
    "pakistan": "PK",
    "qatar": "QA",
    "saudi arabia": "SA",
    "singapore": "SG",
    "spain": "ES",
    "turkey": "TR",
    "turkiye": "TR",
    "uae": "AE",
    "uk": "GB",
    "united arab emirates": "AE",
    "united kingdom": "GB",
    "united states": "US",
    "usa": "US",
    "viet nam": "VN",
    "vietnam": "VN",
    "امارات": "AE",
    "امارات متحده عربی": "AE",
    "هند": "IN",
    "چین": "CN",
    "عراق": "IQ",
    "ترکیه": "TR",
    "اسپانیا": "ES",
    "ایتالیا": "IT",
    "آلمان": "DE",
    "ایران": "IR",
}
_COUNTRY_NAMES.update(
    (name.casefold(), country.alpha_2)
    for country in pycountry.countries
    for name in (country.name, getattr(country, "common_name", country.name))
)
_COUNTRY_MENTIONS = re.compile(
    r"(?<!\w)(?:" + "|".join(map(re.escape, sorted(_COUNTRY_NAMES, key=len, reverse=True))) + r")(?!\w)",
    re.I,
)


def extract_html_tables(raw_html: str, *, max_tables: int = 6, max_rows: int = 40) -> list[dict]:
    """Keep table headers, rows, and the link text that was actually in the page."""

    cleaned = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw_html or "", flags=re.I | re.S)
    tables: list[dict] = []
    for match in _TABLE.finditer(cleaned):
        rows: list[list[str]] = []
        for row_html in _ROW.findall(match.group(1)):
            cells = [_cell_text(cell) for cell in _CELL.findall(row_html)]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(cells)
        if len(rows) < 2:
            continue
        tables.append({"headers": rows[0], "rows": rows[1:max_rows]})
        if len(tables) >= max_tables:
            break
    return tables


def extract_claims(
    *,
    text: str,
    url: str,
    product: str,
    max_claims: int = 8,
    tables: list | None = None,
    hs_code: str | None = None,
    origin: str = "",
    product_terms: list[str] | None = None,
) -> ToolResult:
    raw = (text or "")[:12000]
    sanitized = _INJECTION.sub("[untrusted-text]", raw)
    parsed = [table for table in (tables or []) if isinstance(table, dict)]
    if not parsed and "<table" in sanitized.lower():
        parsed = extract_html_tables(sanitized)
    terms = [product, *(product_terms or [])]
    origin_code = country_code(origin)
    table_claims, rows_seen = _table_claims(
        parsed, url=url, product=product, hs_code=hs_code, terms=terms, origin=origin_code,
        heading=sanitized[:500],
    )
    prose = _sentence_claims(
        sanitized, url=url, product=product, max_claims=max_claims, terms=terms, origin=origin_code,
    )
    claims: list[dict] = []
    seen: set[str] = set()
    ordered = sorted(table_claims, key=lambda claim: _table_rank(claim, hs_code)) + prose
    limit = max(max_claims, 12) if table_claims else max_claims
    for claim in ordered:
        key = str(claim.get("statement") or "").casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        claims.append(claim)
        if len(claims) >= limit:
            break
    if claims:
        outcome = "extracted"
        message = f"{len(claims)} ادعا از متن صفحه استخراج شد. اعداد فقط همان‌هایی است که در صفحه بود."
    elif rows_seen:
        outcome = "irrelevant"
        message = "صفحه خوانده شد. ردیف جدول مرتبط با محصول، کد HS، سال یا اصطلاح تجاری پیدا نشد."
    else:
        outcome = "irrelevant"
        message = "صفحه خوانده شد. ادعای قابل استخراجی در متن نبود."
    return ToolResult(
        tool="extract_claims",
        ok=True,
        message_fa=message,
        data={
            "claims": claims,
            "url": url,
            "outcome": outcome,
            "table_rows_seen": rows_seen,
            "injection_sanitized": bool(_INJECTION.search(raw)),
        },
        provenance=[{"url": url, "publisher": "page", "fetched_at": datetime.now(timezone.utc).isoformat()}],
    )


def _cell_text(raw: str) -> str:
    hrefs = [href for href in _HREF.findall(raw or "") if not href.lower().startswith(("javascript:", "#"))]
    text = html.unescape(_TAG.sub(" ", raw or ""))
    text = _INJECTION.sub("[untrusted-text]", text)
    text = " ".join(text.split())
    if text and hrefs and hrefs[0] not in text and len(text) <= 80:
        text = f"{text} ({hrefs[0][:180]})"
    return text[:240]


def _sentence_claims(
    sanitized: str, *, url: str, product: str, max_claims: int, terms: list[str], origin: str | None
) -> list[dict]:
    prose = " ".join(_TAG.sub(" ", sanitized).split())
    sentences = re.split(r"(?<=[.!?۔؟])\s+", prose)
    claims: list[dict] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 40 or len(sentence) > 400:
            continue
        if not _mentions_product(sentence, terms):
            continue
        countries = country_mentions(sentence) - {origin}
        claims.append(_claim(
            sentence, url=url, product=product, hs_code=None,
            country=next(iter(countries)) if len(countries) == 1 else None,
            period=_period([], [], sentence),
        ))
        if len(claims) >= max_claims:
            break
    return claims


def _table_claims(
    tables: list[dict],
    *,
    url: str,
    product: str,
    hs_code: str | None,
    terms: list[str],
    origin: str | None,
    heading: str,
) -> tuple[list[dict], int]:
    claims: list[dict] = []
    rows_seen = 0
    wanted = re.sub(r"\D", "", hs_code or "")
    path = unquote(urlsplit(url).path)
    product_segment = re.search(r"/product/([0-9]{6})(?:/|$)", path, re.I)
    page_hs = None
    if product_segment and (product_segment[1] == wanted or _mentions_product(heading, terms)):
        page_hs = product_segment[1]
    page_product = bool(page_hs) or _mentions_product(path.replace("-", " "), terms)
    direction = re.search(r"/tradeflow/(imports?|exports?)(?:/|$)", path, re.I)
    imports = bool(direction and direction[1].lower().startswith("import"))
    for table in tables:
        headers = [str(cell) for cell in (table.get("headers") or [])]
        for cells in table.get("rows") or []:
            values = [str(cell).strip() for cell in cells]
            if not any(values):
                continue
            rows_seen += 1
            statement = _row_statement(headers, values)
            codes = hs_codes_in_text(statement)
            if not (
                _mentions_product(statement, terms)
                or (wanted and wanted in codes)
                or (page_product and not codes and _TRADE_WORD.search(statement))
            ):
                continue
            if page_hs and not codes:
                statement = f"HS {page_hs} (source URL); {statement}"
            claims.append(
                _claim(
                    statement,
                    url=url,
                    product=product,
                    hs_code=_row_hs(statement, wanted),
                    country=_market_country(headers, values, origin=origin, imports=imports),
                    period=_period(headers, values, statement),
                )
            )
    return claims, rows_seen


def _row_statement(headers: list[str], cells: list[str]) -> str:
    parts: list[str] = []
    for index, cell in enumerate(cells):
        if not cell:
            continue
        header = headers[index].strip() if index < len(headers) and headers[index].strip() else f"ستون {index + 1}"
        parts.append(f"{header}: {cell}")
    return "; ".join(parts)[:500]


def _mentions_product(text: str, terms: list[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(term.strip())}(?!\w)", text, re.I) for term in terms if term.strip())


def _row_hs(statement: str, wanted_hs: str) -> str | None:
    codes = hs_codes_in_text(statement)
    if wanted_hs and wanted_hs in codes:
        return wanted_hs
    return codes[0] if codes else None


def _period(headers: list[str], cells: list[str], statement: str) -> str | None:
    for header, cell in zip(headers, cells):
        label = header.casefold()
        if "year" in label or "سال" in header:
            found = _YEAR.search(cell)
            if found:
                return found.group(0)
    found = _YEAR.search(statement)
    return found.group(0) if found else None


def _market_country(headers: list[str], cells: list[str], *, origin: str | None, imports: bool) -> str | None:
    reporter = None
    partner = None
    pairs = list(zip(headers, cells))
    if len(cells) > len(headers):
        pairs.extend(
            (f"ستون {index + 1}", cell) for index, cell in enumerate(cells[len(headers):], start=len(headers))
        )
    for header, cell in pairs:
        kind = _header_kind(header)
        if not kind:
            continue
        code = country_code(cell)
        if code is None or code == origin:
            continue
        if kind == "destination":
            return code
        if kind == "partner":
            partner = code
        elif reporter is None:
            reporter = code
    return reporter if imports else partner or reporter


def country_code(text: str) -> str | None:
    key = " ".join(text.casefold().split())
    if key in _COUNTRY_NAMES:
        return _COUNTRY_NAMES[key]
    bare = key.split(" (", 1)[0].strip()
    if bare in _COUNTRY_NAMES:
        return _COUNTRY_NAMES[bare]
    if re.fullmatch(r"[a-z]{2,3}", bare):
        country = pycountry.countries.get(**{"alpha_2" if len(bare) == 2 else "alpha_3": bare.upper()})
        return country.alpha_2 if country else None
    return None


def country_mentions(statement: str) -> set[str]:
    return {_COUNTRY_NAMES[match.group().casefold()] for match in _COUNTRY_MENTIONS.finditer(statement)}


def _header_kind(header: str) -> str:
    label = header.casefold()
    if any(token in label for token in ("destination", "importer", "importing")):
        return "destination"
    if "partner" in label:
        return "partner"
    if any(token in label for token in ("exporter", "exporting")):
        return ""
    if any(token in label for token in ("reporter", "country")):
        return "country"
    return ""


def _claim(
    statement: str,
    *,
    url: str,
    product: str,
    hs_code: str | None,
    country: str | None,
    period: str | None,
) -> dict:
    return {
        "statement": statement,
        "data_kind": "estimate",
        "confidence": "unknown",
        "source_url": url,
        "product": product,
        "country": country,
        "period": period,
        "hs_scope": hs_code,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }


def _table_rank(claim: dict, hs_code: str | None) -> tuple:
    statement = str(claim.get("statement") or "")
    return (
        0 if hs_code and hs_code in statement else 1,
        0 if claim.get("period") else 1,
        0 if claim.get("country") else 1,
    )
