"""Catalog of selectable LLM versions for admin UI.

Keys are stored per model id (encrypted). Active model = selected version.
DEFAULT_LLM_MODEL env sets the initial/fallback selection — not a billing trigger.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LlmModelOption:
    id: str
    label: str
    provider: str  # google | openai | deepseek
    group: str  # UI group key
    group_label_fa: str
    is_flash: bool = False


def _google() -> list[LlmModelOption]:
    g = "google"
    gl = "گوگل (Gemini)"
    rows = [
        ("gemini-2.5-pro", "Gemini 2.5 Pro", False),
        ("gemini-2.5-flash", "Gemini 2.5 Flash", True),
        ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite", True),
        ("gemini-2.5-flash-preview-05-20", "Gemini 2.5 Flash Preview 05-20", True),
        ("gemini-2.5-pro-preview-05-06", "Gemini 2.5 Pro Preview 05-06", False),
        ("gemini-2.0-flash", "Gemini 2.0 Flash", True),
        ("gemini-2.0-flash-001", "Gemini 2.0 Flash 001", True),
        ("gemini-2.0-flash-lite", "Gemini 2.0 Flash-Lite", True),
        ("gemini-2.0-flash-lite-001", "Gemini 2.0 Flash-Lite 001", True),
        ("gemini-2.0-flash-thinking-exp", "Gemini 2.0 Flash Thinking Exp", True),
        ("gemini-2.0-flash-thinking-exp-01-21", "Gemini 2.0 Flash Thinking Exp 01-21", True),
        ("gemini-2.0-pro-exp", "Gemini 2.0 Pro Exp", False),
        ("gemini-2.0-pro-exp-02-05", "Gemini 2.0 Pro Exp 02-05", False),
        ("gemini-1.5-pro", "Gemini 1.5 Pro", False),
        ("gemini-1.5-pro-latest", "Gemini 1.5 Pro Latest", False),
        ("gemini-1.5-pro-002", "Gemini 1.5 Pro 002", False),
        ("gemini-1.5-flash", "Gemini 1.5 Flash", True),
        ("gemini-1.5-flash-latest", "Gemini 1.5 Flash Latest", True),
        ("gemini-1.5-flash-002", "Gemini 1.5 Flash 002", True),
        ("gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B", True),
        ("gemini-1.5-flash-8b-latest", "Gemini 1.5 Flash 8B Latest", True),
        ("gemini-1.0-pro", "Gemini 1.0 Pro", False),
        ("gemini-1.0-pro-001", "Gemini 1.0 Pro 001", False),
        ("gemini-1.0-pro-latest", "Gemini 1.0 Pro Latest", False),
        ("gemini-pro", "Gemini Pro (legacy)", False),
        ("gemini-pro-vision", "Gemini Pro Vision (legacy)", False),
        ("gemini-exp-1206", "Gemini Exp 1206", False),
        ("gemini-exp-1121", "Gemini Exp 1121", False),
        ("learnlm-1.5-pro-experimental", "LearnLM 1.5 Pro Experimental", False),
        ("gemma-3-27b-it", "Gemma 3 27B IT", False),
        ("gemma-3-12b-it", "Gemma 3 12B IT", False),
        ("gemma-3-4b-it", "Gemma 3 4B IT", False),
        ("gemma-3-1b-it", "Gemma 3 1B IT", False),
    ]
    return [
        LlmModelOption(id=i, label=lab, provider=g, group=g, group_label_fa=gl, is_flash=flash)
        for i, lab, flash in rows
    ]


def _openai() -> list[LlmModelOption]:
    g = "openai"
    gl = "اوپن‌ای‌آی (GPT)"
    rows = [
        ("gpt-4.1", "GPT-4.1", False),
        ("gpt-4.1-mini", "GPT-4.1 Mini", False),
        ("gpt-4.1-nano", "GPT-4.1 Nano", False),
        ("gpt-4o", "GPT-4o", False),
        ("gpt-4o-2024-11-20", "GPT-4o 2024-11-20", False),
        ("gpt-4o-2024-08-06", "GPT-4o 2024-08-06", False),
        ("gpt-4o-2024-05-13", "GPT-4o 2024-05-13", False),
        ("gpt-4o-mini", "GPT-4o Mini", False),
        ("gpt-4o-mini-2024-07-18", "GPT-4o Mini 2024-07-18", False),
        ("chatgpt-4o-latest", "ChatGPT-4o Latest", False),
        ("gpt-4-turbo", "GPT-4 Turbo", False),
        ("gpt-4-turbo-2024-04-09", "GPT-4 Turbo 2024-04-09", False),
        ("gpt-4-turbo-preview", "GPT-4 Turbo Preview", False),
        ("gpt-4-0125-preview", "GPT-4 0125 Preview", False),
        ("gpt-4-1106-preview", "GPT-4 1106 Preview", False),
        ("gpt-4", "GPT-4", False),
        ("gpt-4-0613", "GPT-4 0613", False),
        ("gpt-4-32k", "GPT-4 32K", False),
        ("gpt-3.5-turbo", "GPT-3.5 Turbo", False),
        ("gpt-3.5-turbo-0125", "GPT-3.5 Turbo 0125", False),
        ("gpt-3.5-turbo-1106", "GPT-3.5 Turbo 1106", False),
        ("gpt-3.5-turbo-16k", "GPT-3.5 Turbo 16K", False),
        ("o1", "o1", False),
        ("o1-2024-12-17", "o1 2024-12-17", False),
        ("o1-preview", "o1 Preview", False),
        ("o1-mini", "o1 Mini", False),
        ("o1-mini-2024-09-12", "o1 Mini 2024-09-12", False),
        ("o1-pro", "o1 Pro", False),
        ("o3", "o3", False),
        ("o3-mini", "o3 Mini", False),
        ("o3-mini-2025-01-31", "o3 Mini 2025-01-31", False),
        ("o4-mini", "o4 Mini", False),
        ("o4-mini-2025-04-16", "o4 Mini 2025-04-16", False),
        ("gpt-5", "GPT-5", False),
        ("gpt-5-mini", "GPT-5 Mini", False),
        ("gpt-5-nano", "GPT-5 Nano", False),
    ]
    return [
        LlmModelOption(id=i, label=lab, provider=g, group=g, group_label_fa=gl, is_flash=flash)
        for i, lab, flash in rows
    ]


def _deepseek() -> list[LlmModelOption]:
    g = "deepseek"
    gl = "دیپ‌سیک (DeepSeek)"
    rows = [
        ("deepseek-chat", "DeepSeek Chat (V3)", False),
        ("deepseek-reasoner", "DeepSeek Reasoner (R1)", False),
        ("deepseek-coder", "DeepSeek Coder", False),
        ("deepseek-v3", "DeepSeek V3", False),
        ("deepseek-v3.1", "DeepSeek V3.1", False),
        ("deepseek-v3.2", "DeepSeek V3.2", False),
        ("deepseek-r1", "DeepSeek R1", False),
        ("deepseek-r1-0528", "DeepSeek R1 0528", False),
        ("deepseek-r1-lite-preview", "DeepSeek R1 Lite Preview", False),
        ("deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill Llama 70B", False),
        ("deepseek-r1-distill-qwen-32b", "DeepSeek R1 Distill Qwen 32B", False),
        ("deepseek-r1-distill-qwen-14b", "DeepSeek R1 Distill Qwen 14B", False),
        ("deepseek-r1-distill-qwen-7b", "DeepSeek R1 Distill Qwen 7B", False),
        ("deepseek-r1-distill-qwen-1.5b", "DeepSeek R1 Distill Qwen 1.5B", False),
    ]
    return [
        LlmModelOption(id=i, label=lab, provider=g, group=g, group_label_fa=gl, is_flash=flash)
        for i, lab, flash in rows
    ]


def all_models() -> list[LlmModelOption]:
    return [*_google(), *_openai(), *_deepseek()]


def models_by_id() -> dict[str, LlmModelOption]:
    return {m.id: m for m in all_models()}


def catalog_grouped() -> list[dict]:
    """UI payload: groups in display order, Flash shortcuts last."""
    order = [
        ("google", "گوگل (Gemini)"),
        ("openai", "اوپن‌ای‌آی (GPT)"),
        ("deepseek", "دیپ‌سیک (DeepSeek)"),
    ]
    by_group: dict[str, list[LlmModelOption]] = {k: [] for k, _ in order}
    flash: list[LlmModelOption] = []
    for m in all_models():
        by_group.setdefault(m.group, []).append(m)
        if m.is_flash:
            flash.append(m)

    groups: list[dict] = []
    for key, label in order:
        groups.append(
            {
                "id": key,
                "label_fa": label,
                "models": [
                    {
                        "id": m.id,
                        "label": m.label,
                        "provider": m.provider,
                        "is_flash": m.is_flash,
                    }
                    for m in by_group.get(key, [])
                ],
            }
        )
    # Flash convenience group — same model ids / same key slots as primary entries
    groups.append(
        {
            "id": "flash",
            "label_fa": "مدل‌های Flash",
            "models": [
                {
                    "id": m.id,
                    "label": m.label,
                    "provider": m.provider,
                    "is_flash": True,
                }
                for m in flash
            ],
        }
    )
    return groups


def resolve_provider(model_id: str) -> str | None:
    m = models_by_id().get(model_id)
    return m.provider if m else None
