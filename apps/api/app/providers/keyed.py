"""Keyed LLM transports. A call happens only when a caller already reserved budget
and, for research, only after no-cost clearance. This module does not decide that.
"""

from __future__ import annotations

import httpx


def _digits_hs(text: str) -> tuple[str | None, str]:
    digits = "".join(ch for ch in text if ch.isdigit())[:6]
    if len(digits) == 6:
        return digits, "low"
    return None, "unknown"


_HS_PROMPT = (
    "Return ONLY a 6-digit HS code guess for this product, or UNKNOWN. Product: {product}"
)


class KeyedGeminiLLM:
    id = "gemini"
    research_cleared = False

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash", timeout: float = 20.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _generate(self, prompt: str, *, max_tokens: int = 1024) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
                },
            )
        if response.status_code != 200:
            return ""
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
        except Exception:
            return None, "unknown"

    def decide_research_action(self, context: dict) -> str:
        import json

        from app.agents.llm_decide import DECISION_USER_TEMPLATE

        prompt = DECISION_USER_TEMPLATE.format(context=json.dumps(context, ensure_ascii=False))
        return self._generate(prompt, max_tokens=1024)

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
        if response.status_code != 200:
            return ""
        return (response.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        try:
            return _digits_hs(self._chat(_HS_PROMPT.format(product=product), max_tokens=32))
        except Exception:
            return None, "unknown"

    def decide_research_action(self, context: dict) -> str:
        import json

        from app.agents.llm_decide import DECISION_USER_TEMPLATE

        return self._chat(
            DECISION_USER_TEMPLATE.format(context=json.dumps(context, ensure_ascii=False)),
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
