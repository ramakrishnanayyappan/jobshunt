"""Build OpenAI-compatible API base URLs."""
from __future__ import annotations

from jobshunt.models import AISettings


def openai_api_root(a: AISettings) -> str:
    """
    * **openai** (OpenAI.com) with empty base_url: always ``https://api.openai.com/v1`` (public API
      needs ``/v1``; the toggle only affects *custom* bases).
    * **openrouter** with empty base_url: ``https://openrouter.ai/api/v1`` (OpenAI-compatible).
    * **openai_compatible** (corporate / LiteLLM): **base_url is required** — never fall back
      to OpenAI, so you do not get surprise 401s to api.openai.com.
    * If ``openai_use_v1_prefix`` is False, the configured base is used as-is (no extra ``/v1``)
      for *non-empty* custom bases.
    """
    raw = (a.base_url or "").strip()
    if a.provider == "openai_compatible" and not raw:
        raise ValueError(
            "Set Base URL to your company proxy (provider: openai_compatible). "
            "It will not default to api.openai.com."
        )
    if a.provider == "openai" and not raw:
        return "https://api.openai.com/v1"
    if a.provider == "openrouter" and not raw:
        return "https://openrouter.ai/api/v1"
    if not raw:
        b = "https://api.openai.com"
    else:
        b = raw.rstrip("/")
    if a.openai_use_v1_prefix:
        if b.endswith("/v1"):
            return b
        return f"{b}/v1"
    return b
