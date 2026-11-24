"""Keyed LLM transports. A call happens only when a caller already reserved budget.
The admin-selected model is authorized even when the API is billable.
This module does not log keys.
"""

from __future__ import annotations

import re
import time

import httpx

_SECRET = re.compile(r"(AIza[0-9A-Za-z_\-]{8,}|sk-[A-Za-z0-9_\-]{8,}|Bearer\s+\S+)", re.I)


class ModelCallError(RuntimeError):
    """Real endpoint failure. message_fa never includes the API key."""

    def __init__(self, *, status: str, http_status: int | None, message_fa: str):
        self.status = status
        self.http_status = http_status
        self.message_fa = _SECRET.sub("[redacted]", message_fa)[:300]
        super().__init__(self.message_fa)


def _redact(text: str) -> str:
    return _SECRET.sub("[redacted]", text or "")[:180]


# One extra attempt only when the provider sends Retry-After of at most 5s.
# The observed 503 (high demand, ~4s, no Retry-After) is not retried.
_RETRY_AFTER_CAP_S = 5.0


def _status_for(http_status: int, body: str) -> str:
    from app.providers.model_clearance import classify_probe

    return classify_probe(
        provider="",
        model_id="",
        http_status=http_status,
        body=_redact(body),
        error=None,
    )


def _retry_after_seconds(response: object) -> float | None:
    headers = getattr(response, "headers", None) or {}
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    raw = getter("Retry-After")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        seconds = float(str(raw).strip())
    except ValueError:
        return None
    if seconds < 0 or seconds > _RETRY_AFTER_CAP_S:
        return None
    return seconds


def _failure(model_id: str, *, http_status: int | None, body: str = "", error: str | None = None) -> ModelCallError:
    from app.providers.model_clearance import describe_provider_failure

    status = "Failed" if error or http_status is None else _status_for(http_status, body)
    if error and http_status is not None:
        status = _status_for(http_status, body)
    return ModelCallError(
        status=status,
        http_status=http_status,
        message_fa=describe_provider_failure(
            model_id=model_id,
            http_status=http_status,
            body=_redact(body),
            error=error,
        ),
    )


def _digits_hs(text: str) -> tuple[str | None, str]:
    digits = "".join(ch for ch in text if ch.isdigit())[:6]
    if len(digits) == 6:
        return digits, "low"
    return None, "unknown"


_HS_PROMPT = (
    "Return ONLY a 6-digit HS code guess for this product, or UNKNOWN. Product: {product}"
)

# A single float on httpx.Client applies to the read timeout. gemini-4-hydrogen
# generateContent exceeded 20s on both HS classify and the research decision
# (ReadTimeout after an HTTP 503). 120s covers a normal generateContent.
GEMINI_GENERATE_TIMEOUT = 120.0


class KeyedGeminiLLM:
    id = "gemini"
    research_cleared = False

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash", timeout: float = GEMINI_GENERATE_TIMEOUT):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post(self, client: httpx.Client, prompt: str, max_tokens: int) -> httpx.Response:
        return client.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            ),
            headers={"x-goog-api-key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
            },
        )

    def _generate(self, prompt: str, *, max_tokens: int = 1024) -> str:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = self._post(client, prompt, max_tokens)
                # Honor a short Retry-After once. A 503 without that header is not retried.
                if response.status_code in {429, 503}:
                    wait = _retry_after_seconds(response)
                    if wait is not None:
                        time.sleep(wait)
                        response = self._post(client, prompt, max_tokens)
        except httpx.TimeoutException as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        if response.status_code != 200:
            raise _failure(self.model, http_status=response.status_code, body=response.text)
        return (
            response.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            or ""
        )

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        try:
            return _digits_hs(self._generate(_HS_PROMPT.format(product=product), max_tokens=32))
        except ModelCallError:
            raise
        except Exception:
            return None, "unknown"

    def decide_research_action(self, context: dict) -> str:
        from app.agents.llm_decide import render_decision_prompt

        return self._generate(render_decision_prompt(context), max_tokens=1024)

    def complete_json(self, prompt: str) -> str:
        return self._generate(prompt, max_tokens=1024)


class KeyedOpenAICompatLLM:
    """OpenAI Chat Completions — also used for DeepSeek (compatible base URL)."""

    research_cleared = False

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider_id: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ):
        self.id = provider_id
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _chat(self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0) -> str:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
        except httpx.TimeoutException as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        if response.status_code != 200:
            raise _failure(self.model, http_status=response.status_code, body=response.text)
        return (response.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        try:
            return _digits_hs(self._chat(_HS_PROMPT.format(product=product), max_tokens=32))
        except ModelCallError:
            raise
        except Exception:
            return None, "unknown"

    def decide_research_action(self, context: dict) -> str:
        from app.agents.llm_decide import render_decision_prompt

        return self._chat(
            render_decision_prompt(context),
            max_tokens=1024,
            temperature=0.2,
        )

    def complete_json(self, prompt: str) -> str:
        return self._chat(prompt, max_tokens=1024, temperature=0.2)


def build_llm(provider: str, api_key: str, model: str):
    if provider == "google":
        return KeyedGeminiLLM(api_key, model=model)
    if provider == "openai":
        return KeyedOpenAICompatLLM(
            api_key, model, provider_id="openai", base_url="https://api.openai.com/v1"
        )
    if provider == "deepseek":
        return KeyedOpenAICompatLLM(
            api_key,
            model,
            provider_id="deepseek",
            base_url="https://api.deepseek.com/v1",
        )
    # Unknown provider ids are not assumed to be a valid Gemini catalog entry.
    raise ValueError(f"unsupported llm provider: {provider}")


def probe_selected_endpoint(provider: str, model: str, api_key: str, timeout: float = 12.0) -> dict:
    """One real HTTP call to the selected model endpoint. Does not log the key."""

    try:
        with httpx.Client(timeout=timeout) as client:
            if provider == "google":
                response = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": api_key},
                    json={
                        "contents": [{"parts": [{"text": "ping"}]}],
                        "generationConfig": {"temperature": 0, "maxOutputTokens": 1},
                    },
                )
            elif provider == "openai":
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
            elif provider == "deepseek":
                response = client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
            else:
                return {"http_status": None, "error": "unknown_provider", "body": ""}
        return {"http_status": response.status_code, "error": None, "body": response.text[:500]}
    except Exception as exc:
        return {"http_status": None, "error": type(exc).__name__, "body": ""}
