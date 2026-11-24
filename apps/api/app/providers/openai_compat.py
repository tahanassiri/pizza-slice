"""OpenAI-compatible chat for OpenRouter and OmniRouter.

Base URLs come from the vendors' docs. The admin cannot point this client
at an arbitrary host. Research clearance is a separate capability check.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from app.providers.keyed import ModelCallError
from app.providers.model_clearance import describe_provider_failure

# Documented bases only. omnirouter.cc is the docs site, not the API host.
# api.omnirouter.cc and api.omnirouter.ai do not answer.
ROUTER_PROVIDERS: dict[str, dict[str, str]] = {
    "openrouter": {
        "label_fa": "اوپن‌روتر",
        "base_url": "https://openrouter.ai/api/v1",
        "host": "openrouter.ai",
    },
    "omnirouter": {
        "label_fa": "اومنی‌روتر",
        "base_url": "https://omnirouter-api.cc/v1",
        "host": "omnirouter-api.cc",
    },
}

ALLOWED_HOSTS = frozenset(item["host"] for item in ROUTER_PROVIDERS.values())
_MODEL_ID = re.compile(r"^[A-Za-z0-9_.:/~-]{1,160}$")
ROUTER_TIMEOUT = 30.0


class RouterURLError(ValueError):
    def __init__(self, message_fa: str):
        self.message_fa = message_fa
        super().__init__(message_fa)


def is_router(provider_id: str | None) -> bool:
    return provider_id in ROUTER_PROVIDERS


def valid_model_id(model_id: str) -> bool:
    return bool(_MODEL_ID.match(model_id or ""))


def canonical_base(provider_id: str) -> str:
    spec = ROUTER_PROVIDERS.get(provider_id)
    if spec is None:
        raise RouterURLError("ارائه‌دهنده روتر شناخته نشد. مدل دیگری انتخاب نشد.")
    return spec["base_url"]


def assert_router_url(url: str) -> str:
    """HTTPS to openrouter.ai or omnirouter-api.cc, documented path only."""

    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https":
        raise RouterURLError("فقط نشانی HTTPS مجاز است.")
    if parsed.username or parsed.password:
        raise RouterURLError("نشانی نباید نام کاربری یا رمز داشته باشد.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in ALLOWED_HOSTS:
        raise RouterURLError(
            "میزبان مجاز نیست. فقط openrouter.ai و omnirouter-api.cc پذیرفته می‌شوند."
        )
    if parsed.port not in (None, 443):
        raise RouterURLError("فقط درگاه ۴۴۳ مجاز است.")
    expected = urlparse(next(item["base_url"] for item in ROUTER_PROVIDERS.values() if item["host"] == host))
    path = parsed.path.rstrip("/") or "/"
    prefix = expected.path.rstrip("/")
    if path != prefix and not path.startswith(prefix + "/"):
        raise RouterURLError("مسیر با نشانی مستند این میزبان یکی نیست.")
    if parsed.query or parsed.fragment:
        raise RouterURLError("نشانی نباید پارامتر یا قطعه داشته باشد.")
    return f"https://{host}{path}"


def _failure(model_id: str, *, http_status: int | None, body: str = "", error: str | None = None) -> ModelCallError:
    from app.providers.keyed import _status_for

    status = "Failed" if error or http_status is None else _status_for(http_status, body)
    return ModelCallError(
        status=status,
        http_status=http_status,
        message_fa=describe_provider_failure(
            model_id=model_id,
            http_status=http_status,
            body=body[:180],
            error=error,
        ),
    )


class OpenAICompatLLM:
    """Chat completions against one allowlisted router. No second model is chosen."""

    research_cleared = False

    def __init__(self, api_key: str, model: str, *, provider_id: str, timeout: float = ROUTER_TIMEOUT):
        if not is_router(provider_id):
            raise RouterURLError("ارائه‌دهنده روتر شناخته نشد.")
        if not valid_model_id(model):
            raise RouterURLError("شناسه مدل روتر نامعتبر است. مدل دیگری جایگزین نشد.")
        self.id = provider_id
        self.api_key = api_key
        self.model = model
        self.base_url = assert_router_url(canonical_base(provider_id))
        self.timeout = timeout

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> httpx.Response:
        url = assert_router_url(f"{self.base_url}/{path.lstrip('/')}")
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                response = client.request(
                    method,
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=json_body,
                )
        except httpx.TimeoutException as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        if response.status_code in {301, 302, 303, 307, 308}:
            raise ModelCallError(
                status="Failed",
                http_status=response.status_code,
                message_fa="تغییر مسیر پذیرفته نشد. میزبان دیگری باز نشد.",
            )
        return response

    def _chat(self, prompt: str, *, max_tokens: int) -> str:
        response = self._request(
            "POST",
            "chat/completions",
            json_body={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": max_tokens,
            },
        )
        if response.status_code != 200:
            raise _failure(self.model, http_status=response.status_code, body=response.text)
        return (response.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

    def list_model_ids(self) -> list[str]:
        response = self._request("GET", "models")
        if response.status_code != 200:
            raise _failure(self.model or self.id, http_status=response.status_code, body=response.text)
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if rows is None and isinstance(payload, dict):
            rows = payload.get("models")
        ids: list[str] = []
        for item in rows or []:
            if isinstance(item, str) and valid_model_id(item):
                ids.append(item)
            elif isinstance(item, dict):
                mid = item.get("id") or item.get("name")
                if isinstance(mid, str) and valid_model_id(mid):
                    ids.append(mid)
        unique: list[str] = []
        seen: set[str] = set()
        for mid in ids:
            if mid not in seen:
                seen.add(mid)
                unique.append(mid)
            if len(unique) >= 80:
                break
        return unique

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        from app.providers.keyed import _HS_PROMPT, _digits_hs

        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        return _digits_hs(self._chat(_HS_PROMPT.format(product=product), max_tokens=32))

    def decide_research_action(self, context: dict) -> str:
        from app.agents.llm_decide import render_decision_prompt

        return self._chat(render_decision_prompt(context), max_tokens=1024)

    def complete_json(self, prompt: str) -> str:
        return self._chat(prompt, max_tokens=256)
