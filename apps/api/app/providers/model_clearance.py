"""Admin selection authorizes the selected model, paid or free.

A stored key is not proof the endpoint works. Catalog membership is not proof
either. A real request is. Billing is reported separately and does not invent
a no-cost allowlist. NO_COST_LLM_MODELS is not a research gate.
"""

from __future__ import annotations

BILLABLE_PROVIDERS = frozenset({"google", "openai", "deepseek"})

CONNECTION_STATUSES = (
    "Configured",
    "Verified",
    "Failed",
    "Rate-limited",
    "Unavailable",
    "Billing problem",
)

# Historical label written when HTTP 200 was refused for being possibly paid.
# It is not a proven billing failure, so it must not keep blocking research.
_LEGACY_NO_COST_BLOCK = "Billing permission required"


def normalize_connection_status(status: str | None) -> str:
    if status == _LEGACY_NO_COST_BLOCK:
        return "Configured"
    if status in CONNECTION_STATUSES:
        return str(status)
    return "Failed"


def is_research_cleared(model_id: str, connection_status: str) -> bool:
    """True when the admin-selected model may be called inside server budgets.

    Configured means a key is stored and a live probe has not failed.
    Verified means a real request to that endpoint succeeded.
    Paid vs free is not part of this decision.
    """

    del model_id
    return normalize_connection_status(connection_status) in {"Verified", "Configured"}


def classify_probe(*, provider: str, model_id: str, http_status: int | None, body: str, error: str | None) -> str:
    """Map one real endpoint response to a connection or billing status.

    HTTP 200 is Verified for every provider. A billing rejection is
    Billing problem, not a reason to pretend the call was unauthorized
    because the model might cost money.
    """

    del provider, model_id
    if error or http_status is None:
        return "Failed"
    text = (body or "").lower()
    if http_status == 429:
        return "Rate-limited"
    if http_status == 404:
        return "Unavailable"
    billing_words = ("billing", "payment", "permission", "quota", "insufficient", "credit")
    if http_status == 402 or (
        http_status in {400, 401, 403} and any(word in text for word in billing_words)
    ):
        return "Billing problem"
    if http_status in {401, 403}:
        return "Failed"
    if http_status >= 500:
        return "Unavailable"
    if http_status == 200:
        return "Verified"
    return "Failed"


def billing_status_for(connection_status: str) -> str:
    if normalize_connection_status(connection_status) == "Billing problem":
        return "Billing problem"
    return "none"
