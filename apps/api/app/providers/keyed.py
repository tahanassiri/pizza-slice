"""Keyed LLM transports. A call happens only when a caller already reserved budget.
The admin-selected model is authorized even when the API is billable.
This module does not log keys.
"""

from __future__ import annotations

import json
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
        self.tokens_used = 0
        self.output_method = "prompt"

    def _post(
        self,
        client: httpx.Client,
        prompt: str,
        max_tokens: int,
        *,
        schema: dict | None = None,
    ) -> httpx.Response:
        config: dict = {"temperature": 0.2, "maxOutputTokens": max_tokens}
        if schema is not None:
            config["responseMimeType"] = "application/json"
            config["responseSchema"] = schema
        return client.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            ),
            headers={"x-goog-api-key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": config,
            },
        )

    @staticmethod
    def _decision_text(payload: dict) -> tuple[str, str]:
        candidate = (payload.get("candidates") or [{}])[0]
        finish = str(candidate.get("finishReason") or "")
        parts = ((candidate.get("content") or {}).get("parts") or [])
        texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict) or part.get("thought") is True:
                continue
            if isinstance(part.get("text"), str):
                texts.append(part["text"])
        usage = payload.get("usageMetadata") if isinstance(payload.get("usageMetadata"), dict) else {}
        total = usage.get("totalTokenCount")
        return "\n".join(texts), finish if not isinstance(total, int) else finish

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
        payload = response.json()
        text, finish = self._decision_text(payload if isinstance(payload, dict) else {})
        usage = payload.get("usageMetadata") if isinstance(payload, dict) else {}
        if isinstance(usage, dict) and isinstance(usage.get("totalTokenCount"), int):
            self.tokens_used += usage["totalTokenCount"]
        if finish == "MAX_TOKENS" and max_tokens < 8192 and not getattr(self, "_length_retry", False):
            from app.providers.response_norm import extract_json_value

            if extract_json_value(text) is None:
                self._length_retry = True
                try:
                    return self._generate(prompt, max_tokens=min(8192, max(max_tokens * 2, max_tokens + 256)))
                finally:
                    self._length_retry = False
        return text

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
        from app.agents.decision_schema import AGENT_ACTION_JSON_SCHEMA
        from app.agents.llm_decide import render_decision_prompt

        prompt = render_decision_prompt(context)
        correction = str(context.get("_correction") or "")
        if correction:
            prompt += "\n\nValidation feedback: " + correction[:400] + "\nReturn only the corrected JSON object."
        self.output_method = "json_schema"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = self._post(client, prompt, 4096, schema=AGENT_ACTION_JSON_SCHEMA)
                if response.status_code in {400, 404, 422}:
                    self.output_method = "prompt"
                    response = self._post(client, prompt, 4096, schema=None)
        except httpx.TimeoutException as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
        if response.status_code != 200:
            raise _failure(self.model, http_status=response.status_code, body=response.text)
        payload = response.json()
        text, finish = self._decision_text(payload)
        usage = payload.get("usageMetadata") if isinstance(payload.get("usageMetadata"), dict) else {}
        if isinstance(usage.get("totalTokenCount"), int):
            self.tokens_used += usage["totalTokenCount"]
        if finish == "MAX_TOKENS":
            return self._generate(prompt, max_tokens=8192)
        return text

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
        timeout: float = 120.0,
    ):
        self.id = provider_id
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.tokens_used = 0
        self.output_method = "prompt"

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
        from app.agents.decision_schema import AGENT_ACTION_JSON_SCHEMA
        from app.agents.llm_decide import render_decision_prompt
        from app.providers.response_norm import extract_json_value, parse_chat_completion
        from app.providers.structured_request import next_method, parameter_rejected, request_body, select_output_method

        prompt = render_decision_prompt(context)
        correction = str(context.get("_correction") or "")
        method = select_output_method(["structured_outputs", "response_format"])
        tokens = 4096
        length_retried = False
        seen: set[str] = set()
        while method and method not in seen:
            seen.add(method)
            body = request_body(
                model=self.model,
                prompt=prompt,
                method=method,
                schema=AGENT_ACTION_JSON_SCHEMA,
                schema_name="nova_decision",
                max_tokens=tokens,
                correction=correction,
                router_controls=False,
            )
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=body,
                    )
            except httpx.TimeoutException as exc:
                raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
            except httpx.HTTPError as exc:
                raise _failure(self.model, http_status=None, error=type(exc).__name__) from exc
            if parameter_rejected(response.status_code, response.text):
                method = next_method(method)
                continue
            if response.status_code != 200:
                raise _failure(self.model, http_status=response.status_code, body=response.text)
            outcome = parse_chat_completion(response.json(), http_status=200)
            self.tokens_used += int(outcome.usage.get("total_tokens") or 0)
            if outcome.truncated and not length_retried and tokens < 8192:
                length_retried = True
                tokens = 8192
                seen.discard(method)
                continue
            self.output_method = method
            data = extract_json_value(outcome.content)
            if data is None:
                return outcome.content
            return json.dumps(data, ensure_ascii=False)
        self.output_method = "prompt"
        return self._chat(prompt, max_tokens=tokens, temperature=0)

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
