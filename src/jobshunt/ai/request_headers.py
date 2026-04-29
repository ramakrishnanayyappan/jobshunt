"""Shared LLM request header merge — used by client, tests, and custom path APIs."""
from __future__ import annotations

from typing import Dict

from jobshunt.models import AISettings


def merge_llm_request_headers(a: AISettings) -> Dict[str, str]:
    """
    Build headers for outbound OpenAI-style and gateway requests.

    - Strips header names/values (YAML/UI sometimes has stray spaces; gateways require
      exact names, e.g. App-Id).
    - Sets Content-Type consistently.
    - Adds Authorization from api_key when not already present (case-insensitive on name).
    - For **OpenRouter**, adds HTTP-Referer and X-Title when missing (recommended by their API;
      omitting them can cause edge throttling / 429 with no useful log in the dashboard).
    """
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    for x in a.headers:
        name = (x.name or "").strip()
        if not name or name.lower() == "content-type":
            continue
        headers[name] = (x.value or "").strip()
    if a.api_key and a.provider != "ollama" and not any(
        k.lower() == "authorization" for k in headers
    ):
        headers["Authorization"] = f"Bearer {a.api_key}"
    if a.provider == "openrouter":
        if not any(k.lower() == "http-referer" for k in headers):
            headers["HTTP-Referer"] = "http://127.0.0.1:8765"
        if not any(k.lower() == "x-title" for k in headers):
            headers["X-Title"] = "Job Hunt"
    return headers
