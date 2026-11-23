"""Research may call a model only after a verified no-cost clearance.

A stored API key is not clearance. Catalog membership is not clearance.
Google AI subscriptions, including Gemini 4 Hydrogen, are billable unless
an operator explicitly lists that exact model id in NO_COST_LLM_MODELS.
"""

from __future__ import annotations

import os

BILLABLE_PROVIDERS = frozenset({"google", "openai", "deepseek"})

CONNECTION_STATUSES = (
    "Configured",
    "Verified",
    "Failed",
    "Rate-limited",
    "Unavailable",
    "Billing permission required",
)


def proven_no_cost_models() -> set[str]:
    raw = os.environ.get("NO_COST_LLM_MODELS", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def is_research_cleared(model_id: str, connection_status: str) -> bool:
    return connection_status == "Verified" and model_id in proven_no_cost_models()


def classify_probe(*, provider: str, model_id: str, http_status: int | None, body: str, error: str | None) -> str:
    """Map one real endpoint response to an admin connection status.

    HTTP 200 on a billable host is not Verified: the call reached the API,
    but that does not prove the request is free of charge.
    """

    if error or http_status is None:
        return "Failed"
    text = (body or "").lower()
    if http_status == 429:
        return "Rate-limited"
    if http_status == 404:
        return "Unavailable"
    billing_words = ("billing", "payment", "permission", "quota", "insufficient", "credit")
    if http_status == 402 or (
        http_status in {401, 403} and any(word in text for word in billing_words)
    ):
        return "Billing permission required"
    if http_status in {401, 403}:
        return "Failed"
    if http_status >= 500:
        return "Unavailable"
    if http_status == 200:
        if provider in BILLABLE_PROVIDERS and model_id not in proven_no_cost_models():
            return "Billing permission required"
        if model_id in proven_no_cost_models():
            return "Verified"
        return "Billing permission required"
    return "Failed"
