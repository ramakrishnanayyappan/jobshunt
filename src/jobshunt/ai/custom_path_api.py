"""
Non-OpenAI-v1 URL shapes: long path prefix + /responses (Responses API wire) or
+ /chat_completions (path-style chat). Full endpoint if URL already ends with that segment.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional, Tuple

import httpx

from jobshunt.models import AISettings
from jobshunt.ai.request_headers import merge_llm_request_headers

EffectiveFormat = Literal["openai", "responses", "path_chat"]


def _merge_headers(a: AISettings) -> Dict[str, str]:
    return merge_llm_request_headers(a)


def infer_format_from_url(base_url: str) -> Optional[Literal["responses", "path_chat"]]:
    b = (base_url or "").strip().rstrip("/")
    if b.endswith("/responses"):
        return "responses"
    if b.endswith("/chat_completions"):
        return "path_chat"
    return None


def build_custom_url(a: AISettings, fmt: Literal["responses", "path_chat"]) -> str:
    if not (a.base_url or "").strip():
        raise ValueError("Set base_url to your gateway (prefix or full endpoint).")
    b = (a.base_url or "").strip().rstrip("/")
    suff = infer_format_from_url(b)
    if suff == fmt:
        return b
    if fmt == "responses":
        return f"{b}/responses"
    return f"{b}/chat_completions"


def parse_responses_output(out: Dict[str, Any]) -> str:
    output = out.get("output") or []
    if not isinstance(output, list):
        return ""
    parts: List[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for c in item.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "output_text" and c.get("text"):
                parts.append(str(c["text"]).strip())
    return " ".join(parts).strip() if parts else ""


def get_effective_format(a: AISettings) -> Optional[EffectiveFormat]:
    if a.api_format == "openai":
        return "openai"
    if a.api_format == "responses":
        return "responses"
    if a.api_format == "path_chat":
        return "path_chat"
    if a.api_format == "auto":
        inf = infer_format_from_url(a.base_url)
        if inf:
            if inf == "responses":
                return "responses"
            return "path_chat"
        return None
    return "openai"


def _test_payload_responses(a: AISettings) -> Dict[str, Any]:
    return {
        "model": a.model,
        "input": [
            {
                "role": "user",
                "content": "Reply with only the word OK and nothing else.",
                "type": "message",
            }
        ],
    }


def _test_payload_path_chat(a: AISettings) -> Dict[str, Any]:
    return {
        "model": a.model,
        "messages": [
            {"role": "user", "content": "Reply with only the word OK and nothing else."}
        ],
        "max_tokens": a.max_tokens,
    }


def probe_auto_format(
    a: AISettings, timeout: float = 30.0
) -> Tuple[Literal["responses", "path_chat"], str, Dict[str, Any]]:
    if not (a.base_url or "").strip():
        raise ValueError("Set base_url for custom path or auto-detect.")
    b = (a.base_url or "").strip().rstrip("/")
    headers = _merge_headers(a)
    last_error: str = ""
    for fmt, path in [("responses", f"{b}/responses"), ("path_chat", f"{b}/chat_completions")]:
        try:
            body = _test_payload_responses(a) if fmt == "responses" else _test_payload_path_chat(a)
            r = httpx.post(path, headers=headers, json=body, timeout=timeout)
            if r.status_code >= 400:
                last_error = f"{r.status_code} {r.text[:400]!r}"
                continue
            out = r.json()
            if fmt == "responses":
                if "output" in out or parse_responses_output(out):
                    return fmt, path, out
            else:
                ch = (out.get("choices") or [{}])[0] if isinstance(out, dict) else {}
                if isinstance(ch, dict) and (ch.get("message") or {}).get("content") is not None:
                    return fmt, path, out
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError) as e:
            last_error = str(e)[:500]
            continue
    raise ValueError(
        f"auto-detect failed: could not use /responses or /chat_completions. Last: {last_error}"
    )


def persist_api_format(fmtd: Literal["responses", "path_chat"]) -> None:
    from jobshunt.config import load_config, save_config

    c = load_config()
    c.ai = c.ai.model_copy(update={"api_format": fmtd})
    save_config(c)


def test_custom_path(
    a: AISettings, timeout: float = 30.0
) -> Tuple[str, str]:
    """Run test; for auto+prefix, probe and persist api_format. Returns (message, url_used)."""
    eff0 = get_effective_format(a)
    if a.api_format == "auto" and eff0 is None:
        eff, url_used, out = probe_auto_format(a, timeout=timeout)
        persist_api_format(eff)
    else:
        assert eff0 in ("responses", "path_chat")
        eff = eff0
        url_used = build_custom_url(a, eff)
        headers = _merge_headers(a)
        body = _test_payload_responses(a) if eff == "responses" else _test_payload_path_chat(a)
        r = httpx.post(url_used, headers=headers, json=body, timeout=timeout)
        r.raise_for_status()
        out = r.json()
    if eff == "responses":
        snip = (parse_responses_output(out) or str(out)[:200])[:200]
    else:
        ch = (out.get("choices") or [{}])[0]
        snip = (ch.get("message") or {}).get("content", "") or ""
        snip = str(snip)[:200]
    return f"ok ({snip!r})", url_used


def _ensure_auto_resolved(a: AISettings) -> AISettings:
    if a.api_format != "auto":
        return a
    eff = get_effective_format(a)
    if eff in ("responses", "path_chat"):
        return a
    fmt, _, _ = probe_auto_format(a, timeout=120.0)
    persist_api_format(fmt)
    return a.model_copy(update={"api_format": fmt})


def post_custom_path(
    a: AISettings,
    messages: List[Dict[str, str]],
    system: Optional[str],
    temperature: float,
    max_out_tokens: int,
) -> str:
    a = _ensure_auto_resolved(a)
    eff = get_effective_format(a)
    if eff not in ("responses", "path_chat"):
        raise ValueError("post_custom_path needs responses or path_chat after resolve")
    assert eff in ("responses", "path_chat")
    url = build_custom_url(a, eff)
    headers = _merge_headers(a)
    if eff == "responses":
        inp: List[Dict[str, Any]] = []
        if system:
            inp.append({"role": "system", "content": system, "type": "message"})
        for m in messages:
            if m.get("role") == "system":
                continue
            inp.append(
                {
                    "role": m.get("role", "user"),
                    "content": m.get("content", ""),
                    "type": "message",
                }
            )
        body: Dict[str, Any] = {
            "model": a.model,
            "input": inp,
            "max_output_tokens": min(max_out_tokens, 8192),
        }
    else:
        msgs: List[Dict[str, str]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        body = {
            "model": a.model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": min(max_out_tokens, 8000),
        }
    r = httpx.post(url, headers=headers, json=body, timeout=120.0)
    r.raise_for_status()
    out = r.json()
    if eff == "responses":
        return parse_responses_output(out)
    choice = (out.get("choices") or [{}])[0]
    ch = (choice.get("message") or {}).get("content")
    if isinstance(ch, str):
        return ch
    if isinstance(ch, list) and ch:
        return ch[0].get("text", "") if isinstance(ch[0], dict) else str(ch[0])
    return str(ch or "")
