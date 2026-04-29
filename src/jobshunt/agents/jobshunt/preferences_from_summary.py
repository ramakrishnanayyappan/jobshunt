"""LLM: derive career preferences and archetype hints from vault summary text."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings

_SYSTEM = """You analyze a plain-text career / résumé summary for one candidate.

Return ONE JSON object only, no markdown fences, with exactly these keys:
- "user_preferences": array of short strings (one distinct preference per item), e.g. remote-first, no defense sector, staff-level IC, west coast, max 50% travel, etc. Only items grounded in or clearly implied by the summary; if unclear, suggest 3–8 reasonable job-search preference lines a person with this profile might state. Max 20 items.
- "archetype_hints": array of short strings (one per line): role archetypes or focus areas that fit the candidate (e.g. "Backend / distributed systems", "Developer productivity", "Security-minded generalist"). Max 15 items.

Use concise English. Do not invent employers or degrees not present. Valid minified JSON only."""


def _strip_fence(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


def _once_llm(user: str, ai: AISettings) -> str:
    if ai.provider == "anthropic" and ai.api_key:
        from anthropic import Anthropic

        cl = Anthropic(
            api_key=ai.api_key,
            base_url=ai.base_url or "https://api.anthropic.com",
        )
        m = ai.model or "claude-3-5-haiku-20241022"
        cap = min(2000, ai.max_tokens, 4096)
        r = cl.messages.create(
            model=m,
            max_tokens=cap,
            temperature=0.25,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        b0 = r.content[0]
        return b0.text if b0.type == "text" else str(b0)
    return chat_text_impl(
        ai,
        [{"role": "user", "content": user}],
        _SYSTEM,
        2000,
    )


def generate_preferences_from_summary(summary_text: str) -> Tuple[List[str], List[str]]:
    """Returns (user_preferences, archetype_hints)."""
    snippet = (summary_text or "").strip()
    if not snippet:
        return [], []
    if len(snippet) > 48_000:
        snippet = snippet[:48_000] + "\n…(truncated)"
    user = f"--- CAREER SUMMARY ---\n{snippet}\n"

    def _call(a: AISettings) -> str:
        return _once_llm(user, a)

    raw = run_with_llm_fallback("jobshunt", _call)
    text = _strip_fence(raw)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return [], []
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return [], []
    if not isinstance(obj, dict):
        return [], []

    def _lines(key: str, cap: int) -> List[str]:
        v = obj.get(key)
        if not isinstance(v, list):
            return []
        out: List[str] = []
        for x in v:
            if isinstance(x, str) and x.strip():
                out.append(x.strip()[:500])
            if len(out) >= cap:
                break
        return out

    return _lines("user_preferences", 25), _lines("archetype_hints", 20)

