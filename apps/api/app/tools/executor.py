"""Allowlisted tool executor with budget + audit."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.policy import ALLOWED_TOOLS
from app.agents.tool_contracts import ToolCall, ToolResult
from app.knowledge.repository import KnowledgeRepository
from app.tools import budget as budget_mod
from app.tools.official_trade import get_trade_stats
from app.tools.page_fetch import fetch_page
from app.tools.verify_company import verify_company
from app.tools.web_search import search_web
from app.services.feasibility_calc import recompute, default_feasibility_template
from app.schemas.contracts import Feasibility


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
        self.search = search
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

        # consume budget after success/attempt based on spent hints
        for kind, units in (result.spent or {}).items():
            try:
                budget_mod.consume(
                    self.db,
                    self.budget,
                    kind=kind,
                    units=int(units),
                    run_id=self.run_id,
                    provider_id=str((result.data or {}).get("provider_id") or call.tool),
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
        # model calls without spent still count when classify
        if call.tool == "classify_product" and "model" not in (result.spent or {}):
            try:
                budget_mod.consume(
                    self.db,
                    self.budget,
                    kind="model",
                    units=1,
                    run_id=self.run_id,
                    provider_id="llm",
                    tool_name=call.tool,
                    ok=result.ok,
                )
            except budget_mod.BudgetExceeded as exc:
                return ToolResult(
                    tool=call.tool,
                    ok=False,
                    message_fa=exc.message_fa,
                    error_code=exc.code,
                )
        return result

    def _dispatch(self, tool: str, args: dict[str, Any]) -> ToolResult:
        if tool == "search_web":
            return search_web(
                self.search,
                query=str(args.get("query") or ""),
                country=args.get("country"),
                max_results=int(args.get("max_results") or 5),
            )
        if tool == "fetch_page":
            before = self.budget.pages_used
            if before >= self.budget.max_pages:
                raise budget_mod.BudgetExceeded("سقف خواندن صفحه تمام شد.")
            return fetch_page(str(args.get("url") or ""))
        if tool == "get_trade_stats":
            return get_trade_stats(
                self.trade_service,
                product=str(args.get("product") or ""),
                origin=str(args.get("origin") or "ایران"),
                hs6=args.get("hs6"),
            )
        if tool == "read_memory":
            item, status = self.memory.lookup_public(
                kind=str(args.get("kind") or "analysis"),
                product=args.get("product"),
                hs6=args.get("hs6"),
                origin=args.get("origin"),
                destination=args.get("destination"),
                metric=args.get("metric"),
                period=args.get("period"),
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
            # handled at runner level usually; allow writing public market analysis
            payload = args.get("payload") or {}
            if not isinstance(payload, dict):
                return ToolResult(
                    tool="save_evidence",
                    ok=False,
                    message_fa="payload نامعتبر",
                    error_code="INVALID_ARGS",
                )
            item = self.memory.save_public(
                kind=str(args.get("kind") or "analysis"),
                payload=payload,
                product=args.get("product"),
                hs6=args.get("hs6"),
                origin=args.get("origin"),
                destination=args.get("destination"),
                metric=args.get("metric"),
                period=args.get("period"),
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
            if self.llm and hasattr(self.llm, "classify_hs"):
                hs, conf = self.llm.classify_hs(product, hs_hint)
            elif hs_hint:
                hs, conf = str(hs_hint), "medium"
            return ToolResult(
                tool="classify_product",
                ok=True,
                message_fa="طبقه‌بندی محصول انجام شد.",
                data={"hs_code": hs, "hs_confidence": conf, "product": product},
                spent={"model": 1},
            )
        if tool == "research_regulations":
            # Best-effort web search; never invent legal conclusions
            q = (
                f"{args.get('product')} {args.get('hs') or ''} import regulations "
                f"{args.get('destination') or ''} from {args.get('origin') or 'Iran'}"
            )
            return search_web(self.search, query=q, country=args.get("destination"), max_results=4)
        if tool == "research_logistics":
            q = (
                f"freight shipping cost estimate {args.get('origin') or 'Iran'} to "
                f"{args.get('destination') or ''} {args.get('product') or ''} {args.get('incoterm') or 'FOB'}"
            )
            return search_web(self.search, query=q, max_results=4)
        return ToolResult(
            tool=tool,
            ok=False,
            message_fa="ابزار پیاده‌سازی نشده.",
            error_code="TOOL_NOT_IMPLEMENTED",
        )
