"""Buyer/company verification — reject seller-only SEO listings."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.agents.tool_contracts import ToolResult
from app.tools.page_fetch import fetch_page

SELLER_PATTERNS = re.compile(
    r"\b(for sale|sell(ing)?|exporter|wholesale price list|exporting from|"
    r"we (export|sell|supply)|manufacturer.?exporter|alibaba|made-in-china|"
    r"فروش|صادرکننده|تولید و فروش)\b",
    re.I,
)
BUYER_PATTERNS = re.compile(
    r"\b(import(er|ing)?|distributor|wholesaler|procurement|sourcing|"
    r"buy(ing)?|purchasing|supplier portal|RFQ|"
    r"واردکننده|توزیع|عمده‌فروش|خرید)\b",
    re.I,
)
DIRECTORY_HOSTS = {
    "alibaba.com",
    "made-in-china.com",
    "globenewswire.com",
    "yellowpages.com",
    "indiamart.com",
    "tradekey.com",
    "exportersindia.com",
}


def _domain(url: str | None) -> str:
    if not url:
        return ""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host


def classify_category(text: str) -> str:
    t = text.lower()
    if re.search(r"distribut", t) or "توزیع" in text:
        return "distributor"
    if re.search(r"wholesale", t) or "عمده" in text:
        return "wholesaler"
    if re.search(r"manufacturer|factory|industrial|کارخانه|صنعتی", t):
        return "industrial_end_user"
    if re.search(r"import", t) or "وارد" in text:
        return "importer"
    return "unknown"


def verify_company(
    *,
    company_name: str,
    website: str | None,
    country: str,
    product: str,
    snippets: list[str] | None = None,
    fetch: bool = True,
) -> ToolResult:
    domain = _domain(website)
    joined = " ".join([company_name, *(snippets or [])])
    if domain and any(domain.endswith(h) for h in DIRECTORY_HOSTS):
        return ToolResult(
            tool="verify_company",
            ok=True,
            message_fa="فهرست/آگهی فروش — به‌عنوان خریدار تأیید نمی‌شود.",
            data={
                "company_name": company_name,
                "website": website,
                "country": country,
                "verification_status": "rejected",
                "category": "directory",
                "reason_fa": "دامنه آگهی/دایرکتوری فروشنده",
                "purchase_intent": None,
            },
        )

    page_text = ""
    provenance = []
    if fetch and website:
        page = fetch_page(website)
        if page.ok:
            page_text = str(page.data.get("text") or "")
            provenance = page.provenance
            joined = f"{joined} {page_text[:3000]}"
        else:
            # cannot verify without page → needs_review
            return ToolResult(
                tool="verify_company",
                ok=True,
                message_fa="صفحه شرکت خوانده نشد — نیازمند بررسی.",
                data={
                    "company_name": company_name,
                    "website": website,
                    "country": country,
                    "verification_status": "needs_review",
                    "category": classify_category(joined),
                    "reason_fa": page.message_fa,
                    "fit_evidence": (snippets or [])[:3],
                },
                provenance=[{"url": website, "error": page.error_code}],
                spent=page.spent,
            )

    sellerish = bool(SELLER_PATTERNS.search(joined))
    buyerish = bool(BUYER_PATTERNS.search(joined))
    category = classify_category(joined)

    if sellerish and not buyerish:
        status = "rejected"
        category = "seller"
        reason = "علائم فروشنده/صادرکننده بدون نقش خریدار"
    elif buyerish and website and page_text:
        status = "source_backed"
        reason = "نقش خریدار/توزیع با صفحه شرکت هم‌خوان است"
    elif buyerish:
        status = "needs_review"
        reason = "علائم خریدار در اسنیپت؛ صفحه رسمی ناکافی"
    else:
        status = "needs_review"
        reason = "نقش کسب‌وکار مبهم"

    fit = []
    if snippets:
        fit.extend(snippets[:2])
    if page_text:
        fit.append(f"بررسی صفحه رسمی ({domain})")
    fit.append(f"محصول هدف: {product}")

    return ToolResult(
        tool="verify_company",
        ok=True,
        message_fa=f"وضعیت اعتبارسنجی: {status}",
        data={
            "company_name": company_name,
            "website": website,
            "country": country,
            "verification_status": status,
            "category": category,
            "reason_fa": reason,
            "fit_evidence": fit,
            "purchase_intent": None,
            "business_type_fa": {
                "importer": "واردکننده",
                "distributor": "توزیع‌کننده",
                "wholesaler": "عمده‌فروش",
                "industrial_end_user": "مصرف‌کننده صنعتی",
                "unknown": "نقش نامشخص",
            }.get(category, "نقش نامشخص"),
        },
        provenance=provenance,
        spent={"page": 1} if page_text else {},
    )
