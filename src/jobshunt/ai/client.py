from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypeVar

import httpx

from jobshunt.config import load_config
from jobshunt.models import AISettings
from jobshunt.ai.openai_url import openai_api_root
from jobshunt.ai.request_headers import merge_llm_request_headers
from jobshunt.ai.resolve import resolve_ai_settings, resolve_llm_chain

T = TypeVar("T")


def get_ai_settings(agent: Optional[str] = None) -> AISettings:
    if agent:
        return resolve_ai_settings(agent)
    return load_config().ai.model_copy(deep=True)


def run_with_llm_fallback(agent: Optional[str], fn: Callable[[AISettings], T]) -> T:
    chain = resolve_llm_chain(agent)
    last_exc: Optional[BaseException] = None
    for a in chain:
        try:
            return fn(a)
        except BaseException as e:
            last_exc = e
            continue
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("resolve_llm_chain returned empty")


def chat_text_impl(
    a: AISettings,
    messages: List[Dict[str, str]],
    system: Optional[str],
    max_out_tokens: Optional[int],
) -> str:
    if max_out_tokens is not None:
        eff_cap = min(int(max_out_tokens), int(a.max_tokens), 8000)
    else:
        eff_cap = min(a.max_tokens, 2000)
    if a.provider in ("openai", "openai_compatible") and a.api_format in (
        "responses",
        "path_chat",
        "auto",
    ):
        from jobshunt.ai.custom_path_api import post_custom_path

        return post_custom_path(
            a,
            messages,
            system,
            a.temperature,
            eff_cap,
        )
    a_use = a
    if a.provider == "ollama" and not (a.base_url or "").strip():
        a_use = a.model_copy(
            update={"base_url": "http://127.0.0.1:11434", "openai_use_v1_prefix": True}
        )
    b = openai_api_root(a_use)
    body: Dict[str, Any] = {
        "model": a_use.model,
        "messages": (
            ([{"role": "system", "content": system}] if system else [])
            + [m for m in messages if m.get("role") != "system"]
        ),
        "temperature": a_use.temperature,
        "max_tokens": eff_cap,
    }
    h = merge_llm_request_headers(a_use)
    r = httpx.post(
        f"{b}/chat/completions",
        headers=h,
        json=body,
        timeout=120.0 if eff_cap > 2000 else 60.0,
    )
    r.raise_for_status()
    d = r.json()
    ch = d["choices"][0]["message"]["content"]
    if isinstance(ch, str):
        return ch
    return ch[0].get("text", "")


def chat_text(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    *,
    max_out_tokens: Optional[int] = None,
    agent: Optional[str] = None,
) -> str:
    return run_with_llm_fallback(
        agent,
        lambda a: chat_text_impl(a, messages, system, max_out_tokens),
    )
