"""Structured tool I/O contracts — LLM proposes; server validates & executes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    ok: bool
    message_fa: str = ""
    error_code: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    spent: dict[str, int] = Field(default_factory=dict)


class ResearchPlan(BaseModel):
    questions: list[str] = Field(default_factory=list)
    candidate_countries: list[str] = Field(default_factory=list)
    tools_needed: list[str] = Field(default_factory=list)
    notes_fa: str = ""


class ScoreCriterion(BaseModel):
    key: str
    score_value: float | None = None  # 0..1 or None if unknown
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    unknown: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    date_scope: str | None = None
    note_fa: str = ""

    @field_validator("score_value")
    @classmethod
    def bound_score(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if v < 0 or v > 1:
            raise ValueError("score_value must be in [0,1]")
        return v


class MarketScoreCard(BaseModel):
    country_code: str
    criteria: list[ScoreCriterion] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    total: float | None = None
    recommendation: Literal["recommended", "risky", "watch"] = "watch"
    data_scope: Literal["hs6", "product_family", "sector", "total", "qualitative"] = "sector"
    rationale_fa: list[str] = Field(default_factory=list)


class BuyerCandidateIn(BaseModel):
    company_name: str
    website: str | None = None
    country: str
    category: Literal[
        "importer", "distributor", "wholesaler", "industrial_end_user", "unknown"
    ] = "unknown"
    snippets: list[str] = Field(default_factory=list)


class StageOutput(BaseModel):
    stage: str
    status: Literal["completed", "partial", "failed", "needs_user_input"]
    findings: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    next_action: str | None = None
    spent_budget: dict[str, int] = Field(default_factory=dict)
