"""Allowlisted tool executor — budget checked BEFORE side-effecting calls."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.policy import ALLOWED_TOOLS
from app.agents.tool_contracts import ToolCall, ToolResult
from app.core.config import get_settings
from app.knowledge.repository import KnowledgeRepository
from app.schemas.contracts import Feasibility
from app.services.feasibility_calc import default_feasibility_template, recompute
from app.tools import budget as budget_mod
from app.tools.credibility import assess_credibility, cross_check_claims
from app.tools.extract import extract_claims
from app.tools.budget import guarded_model_call
from app.tools.free_web import free_web_search
from app.tools.page_fetch import fetch_page
from app.tools.verify_company import verify_company


class ToolExecutor:
    def __init__(
        self,
        db: Session,
        *,
        run_id: str,
        search: object | None = None,
        trade_service: object | None = None,
        llm: object | None = None,
    ):
        self.db = db
        self.run_id = run_id
        self.search = search  # optional legacy adapter; free_web is primary
        self.trade_service = trade_service
        self.llm = llm
        self.budget = budget_mod.ensure_run_budget(db, run_id)
        self.memory = KnowledgeRepository(db)

    def execute(self, call: ToolCall) -> ToolResult:
        if call.tool not in ALLOWED_TOOLS:
            return ToolResult(
                tool=call.tool,
                ok=False,
                message_fa="ابزار مجاز نیست.",
                error_code="TOOL_NOT_ALLOWED",
            )
        try:
            result = self._dispatch(call.tool, call.args or {})
        except budget_mod.BudgetExceeded as exc:
            return ToolResult(
                tool=call.tool,
                ok=False,
                message_fa=exc.message_fa,
                error_code=exc.code,
            )
        except Exception as exc:
            return ToolResult(
                tool=call.tool,
                ok=False,
                message_fa=f"خطای ابزار ({type(exc).__name__}).",
                error_code="TOOL_ERROR",
            )

        spent = dict(result.spent or {})
        if (
            call.tool == "classify_product"
            and not (result.data or {}).get("budget_reserved")
            and "model" not in spent
        ):
            spent["model"] = 1
        for kind, units in spent.items():
            try:
                budget_mod.consume(
                    self.db,
                    self.budget,
                    kind=kind,
                    units=int(units),
                    run_id=self.run_id,
                    provider_id=str((result.data or {}).get("provider") or call.tool),
                    tool_name=call.tool,
                    ok=result.ok,
                    detail_fa=result.message_fa[:200],
                )
            except budget_mod.BudgetExceeded as exc:
                return ToolResult(
                    tool=call.tool,
                    ok=False,
                    message_fa=exc.message_fa,
                    error_code=exc.code,
                    data=result.data,
                )
        return result

    def _dispatch(self, tool: str, args: dict[str, Any]) -> ToolResult:
        stub = (get_settings().provider_mode or "").lower() == "stub"
        if tool == "search_web":
            if stub:
                return ToolResult(
                    tool="search_web",
                    ok=False,
                    message_fa="حالت stub — تماس وب خارجی انجام نشد (بدون جعل نتیجه).",
                    error_code="INSUFFICIENT_EVIDENCE",
                    spent={"search": 1},
                )
            followups = args.get("followups") if isinstance(args.get("followups"), list) else None
            return free_web_search(
                str(args.get("query") or ""),
                max_results=min(8, int(args.get("max_results") or 5)),
                country=args.get("country"),
                followups=[str(item) for item in (followups or [])][:2],
            )
        if tool == "fetch_page":
            if stub:
                return ToolResult(
                    tool="fetch_page",
                    ok=False,
                    message_fa="حالت stub — واکشی صفحه انجام نشد.",
                    error_code="PAGE_UNAVAILABLE",
                    spent={"page": 1},
                )
            return fetch_page(str(args.get("url") or ""))
        if tool == "extract_claims":
            return extract_claims(
                text=str(args.get("text") or ""),
                url=str(args.get("url") or ""),
                product=str(args.get("product") or ""),
            )
        if tool == "assess_credibility":
            return assess_credibility(
                url=str(args.get("url") or ""),
                title=str(args.get("title") or ""),
                publisher=str(args.get("publisher") or ""),
            )
        if tool == "cross_check":
            return cross_check_claims(list(args.get("claims") or []))
        if tool == "get_trade_stats":
            # Not a mandatory integration — honest unavailable; agent should use web discovery
            return ToolResult(
                tool="get_trade_stats",
                ok=False,
                message_fa=(
                    "آمار تجارت سخت‌کدشده (WITS/Comtrade) از مسیر ایجنت حذف شده است. "
                    "از جست‌وجوی وب و منابع عمومی کشف‌شده استفاده کنید."
                ),
                error_code="PROVIDER_UNAVAILABLE",
                data={"hint": "use search_web + fetch_page"},
            )
        if tool == "read_memory":
            item, status = self.memory.lookup_public(
                kind=str(args.get("kind") or "analysis"),
                product=args.get("product"),
                hs6=args.get("hs6"),
                origin=args.get("origin"),
                destination=args.get("destination"),
                metric=args.get("metric"),
                period=args.get("period") if args.get("period") is not None else "",
            )
            return ToolResult(
                tool="read_memory",
                ok=True,
                message_fa=f"حافظه: {status}",
                data={
                    "status": status,
                    "item": None
                    if not item
                    else {
                        "id": item.id,
                        "canonical_key": item.canonical_key,
                        "payload": item.payload_json,
                        "fetched_at": item.fetched_at.isoformat() if item.fetched_at else None,
                        "stale_after": item.stale_after.isoformat() if item.stale_after else None,
                        "confidence": item.confidence,
                        "published_period": item.published_period,
                        "version": item.version,
                    },
                },
            )
        if tool == "save_evidence":
            payload = args.get("payload") or {}
            if not isinstance(payload, dict):
                return ToolResult(
                    tool="save_evidence",
                    ok=False,
                    message_fa="payload نامعتبر",
                    error_code="INVALID_ARGS",
                )
            period = args.get("period") if args.get("period") is not None else ""
            item = self.memory.save_public(
                kind=str(args.get("kind") or "analysis"),
                payload=payload,
                product=args.get("product"),
                hs6=args.get("hs6"),
                origin=args.get("origin"),
                destination=args.get("destination"),
                metric=args.get("metric"),
                period=period,
                confidence=str(args.get("confidence") or "low"),
                origin_run_id=self.run_id,
                published_period=args.get("published_period"),
            )
            return ToolResult(
                tool="save_evidence",
                ok=True,
                message_fa="در حافظه عمومی ذخیره شد.",
                data={"knowledge_id": item.id, "version": item.version},
            )
        if tool == "verify_company":
            return verify_company(
                company_name=str(args.get("company_name") or ""),
                website=args.get("website"),
                country=str(args.get("country") or ""),
                product=str(args.get("product") or ""),
                snippets=list(args.get("snippets") or []),
                fetch=bool(args.get("fetch", True)),
            )
        if tool == "calculate_economics":
            raw = args.get("feasibility")
            feas = Feasibility.model_validate(raw) if raw else default_feasibility_template()
            out = recompute(feas)
            return ToolResult(
                tool="calculate_economics",
                ok=True,
                message_fa="محاسبه قطعی انجام شد.",
                data={"feasibility": out.model_dump()},
            )
        if tool == "classify_product":
            product = str(args.get("product") or "")
            hs_hint = args.get("hs_hint")
            hs, conf = None, "unknown"
            reserved = False
            cleared = bool(self.llm) and bool(getattr(self.llm, "research_cleared", False))
            stub_llm = bool(self.llm) and getattr(self.llm, "id", "") == "stub_llm"
            if self.llm and hasattr(self.llm, "classify_hs") and (cleared or stub_llm):
                try:
                    hs, conf = guarded_model_call(
                        self.db,
                        self.run_id,
                        "classify",
                        lambda: self.llm.classify_hs(product, hs_hint),  # type: ignore[union-attr]
                        provider_id=str(getattr(self.llm, "id", "llm")),
                    )
                except Exception as exc:
                    from app.providers.keyed import ModelCallError

                    if isinstance(exc, ModelCallError):
                        code = {
                            "Billing problem": "MODEL_BILLING",
                            "Rate-limited": "MODEL_RATE_LIMITED",
                            "Unavailable": "MODEL_UNAVAILABLE",
                        }.get(exc.status, "MODEL_FAILED")
                        return ToolResult(
                            tool="classify_product",
                            ok=False,
                            message_fa=exc.message_fa,
                            error_code=code,
                            data={"product": product, "budget_reserved": True},
                            spent={},
                        )
                    raise
                reserved = True
                self.budget = budget_mod.ensure_run_budget(self.db, self.run_id)
            elif hs_hint:
                hs, conf = str(hs_hint), "medium"
            return ToolResult(
                tool="classify_product",
                ok=True,
                message_fa="طبقه‌بندی محصول انجام شد.",
                data={
                    "hs_code": hs,
                    "hs_confidence": conf,
                    "product": product,
                    "budget_reserved": reserved,
                },
                spent={},
            )
        if tool in {"research_regulations", "research_logistics"}:
            if stub:
                return ToolResult(
                    tool=tool,
                    ok=False,
                    message_fa="حالت stub — جست‌وجوی مقررات/حمل انجام نشد.",
                    error_code="INSUFFICIENT_EVIDENCE",
                    spent={"search": 1},
                )
            if tool == "research_regulations":
                q = (
                    f"{args.get('product')} {args.get('hs') or ''} import regulations "
                    f"{args.get('destination') or ''} from {args.get('origin') or 'Iran'}"
                )
            else:
                q = (
                    f"freight shipping cost estimate {args.get('origin') or 'Iran'} to "
                    f"{args.get('destination') or ''} {args.get('product') or ''} "
                    f"{args.get('incoterm') or 'FOB'}"
                )
            return free_web_search(q, max_results=4, country=args.get("destination"))
        return ToolResult(
            tool=tool,
            ok=False,
            message_fa="ابزار پیاده‌سازی نشده.",
            error_code="TOOL_NOT_IMPLEMENTED",
        )
