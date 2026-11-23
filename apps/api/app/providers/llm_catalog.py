"""Catalog of selectable LLM versions for admin UI (current API IDs only).

Keys are stored per model id (encrypted). Active model = selected version.
DEFAULT_LLM_MODEL env sets the initial/fallback selection — not a billing trigger.

Freshness floor (Nov 2026):
- Google: Gemini 3 Flash / 3.x Flash-Lite / 3.8 Flash and upward (no 1.5 / 2.0 / 2.5)
- OpenAI: GPT-6 family (+ recent GPT-5.x still active); no GPT-3.5 / 4 / 4o / o1
- DeepSeek: V4 Flash/Pro (+ flash alias); no chat/reasoner/V3 distill legacy
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
    # Current / recent only — Gemini 3 Flash floor and 3.8 Flash upward
    rows = [
        ("gemini-3.8-flash", "Gemini 3.8 Flash", True),
        ("gemini-3.8-live", "Gemini 3.8 Live", True),
        ("gemini-3.8-live-extended-thinking", "Gemini 3.8 Live Extended Thinking", True),
        ("gemini-3.6-flash", "Gemini 3.6 Flash", True),
        ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", True),
        ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite", True),
        ("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview", False),
        ("gemini-3-flash-preview", "Gemini 3 Flash Preview", True),
        ("gemini-3-pro-image", "Gemini 3 Pro Image (Nano Banana Pro)", False),
        ("gemini-3.1-flash-image", "Gemini 3.1 Flash Image (Nano Banana 2)", True),
        ("gemini-3.1-flash-lite-image", "Gemini 3.1 Flash-Lite Image", True),
        ("gemini-4-argon", "Gemini 4 Argon", False),
        ("gemini-4-carbon", "Gemini 4 Carbon", False),
        ("gemini-4-neon", "Gemini 4 Neon", False),
        ("gemini-4-hydrogen", "Gemini 4 Hydrogen", False),
    ]
    return [
        LlmModelOption(id=i, label=lab, provider=g, group=g, group_label_fa=gl, is_flash=flash)
        for i, lab, flash in rows
    ]


def _openai() -> list[LlmModelOption]:
    g = "openai"
    gl = "اوپن‌ای‌آی (GPT)"
    # Current flagship + recent active GPT-5.x / GPT-6 family (no 3.5 / 4 / 4o / o-series)
    rows = [
        ("gpt-6.2-astra", "GPT-6.2 Astra", False),
        ("gpt-6.2-sol", "GPT-6.2 Sol", False),
        ("gpt-6.1-terra", "GPT-6.1 Terra", False),
        ("gpt-6.1-sol", "GPT-6.1 Sol", False),
        ("gpt-6-sol", "GPT-6 Sol", False),
        ("gpt-6-luna", "GPT-6 Luna", False),
        ("gpt-5.6-sol", "GPT-5.6 Sol", False),
        ("gpt-5.6-terra", "GPT-5.6 Terra", False),
        ("gpt-5.6-luna", "GPT-5.6 Luna", False),
        ("gpt-5.6", "GPT-5.6 (alias → Sol)", False),
        ("gpt-5.5", "GPT-5.5", False),
        ("gpt-5.5-pro", "GPT-5.5 Pro", False),
        ("gpt-5.4", "GPT-5.4", False),
        ("gpt-5.4-pro", "GPT-5.4 Pro", False),
        ("gpt-5.4-mini", "GPT-5.4 Mini", False),
        ("gpt-5.4-nano", "GPT-5.4 Nano", False),
        ("gpt-5.3-chat-latest", "GPT-5.3 Chat Latest", False),
        ("gpt-5.2", "GPT-5.2", False),
        ("gpt-5.2-chat-latest", "GPT-5.2 Chat Latest", False),
        ("gpt-5.1", "GPT-5.1", False),
        ("gpt-5", "GPT-5", False),
        ("gpt-5-mini", "GPT-5 Mini", False),
        ("gpt-5-nano", "GPT-5 Nano", False),
        ("gpt-5-pro", "GPT-5 Pro", False),
    ]
    return [
        LlmModelOption(id=i, label=lab, provider=g, group=g, group_label_fa=gl, is_flash=flash)
        for i, lab, flash in rows
    ]


def _deepseek() -> list[LlmModelOption]:
    g = "deepseek"
    gl = "دیپ‌سیک (DeepSeek)"
    # Latest API IDs only (V4 Flash/Pro era). Legacy chat/reasoner/V3 distill removed.
    rows = [
        ("deepseek-flash", "DeepSeek Flash (V4.1 Flash)", True),
        ("deepseek-v4-pro", "DeepSeek V4 Pro", False),
        ("deepseek-v4-flash", "DeepSeek V4 Flash (alias → Flash)", True),
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
