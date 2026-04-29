from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jobshunt.config import apply_agent_llm_defaults, load_config, save_config
from jobshunt.models import (
    AIPublicSettings,
    AIPublicSettingsView,
    AIApiFormat,
    AgentLLMBinding,
    LLMProfile,
    LLMProfilePublic,
    JobShuntAppConfig,
    ProfileEditorView,
    AISettings,
    AIHeaderModel,
    AIProvider,
)
from jobshunt.ai.constants import KNOWN_AGENTS
from jobshunt.ai.request_headers import merge_llm_request_headers
from jobshunt.ai.resolve import (
    normalize_agent_llm,
    strip_bindings_for_deleted_profile,
)

router = APIRouter(prefix="/api/settings/ai", tags=["ai"])


def _finalize_and_validate_bindings(c: JobShuntAppConfig) -> None:
    """Auto-fill missing primaries when possible; require a valid primary per agent if any profiles exist."""
    apply_agent_llm_defaults(c)
    known = {p.id for p in c.llm_profiles}
    if not known:
        return
    for agent in KNOWN_AGENTS:
        b = c.agent_llm.get(agent) or AgentLLMBinding()
        pid = (b.primary_profile_id or "").strip()
        if pid not in known:
            raise HTTPException(
                400,
                "Choose a primary saved model for JobShunt under AI settings, then click Save agent routing.",
            ) from None


def _to_public(s: AISettings) -> AIPublicSettings:
    return AIPublicSettings(
        provider=s.provider,
        base_url=s.base_url,
        has_api_key=bool(s.api_key),
        model=s.model,
        headers=s.headers,
        temperature=s.temperature,
        max_tokens=s.max_tokens,
        openai_use_v1_prefix=s.openai_use_v1_prefix,
        api_format=s.api_format,
    )


def _profile_public(p: LLMProfile) -> LLMProfilePublic:
    a = p.settings
    return LLMProfilePublic(
        id=p.id,
        name=p.name,
        provider=a.provider,
        model=a.model,
        api_format=a.api_format,
        base_url=a.base_url,
        has_api_key=bool(a.api_key),
    )


def _to_view(c) -> AIPublicSettingsView:
    base = _to_public(c.ai)
    known = {p.id for p in c.llm_profiles}
    active = c.active_llm_profile_id
    if active and active not in known:
        active = None
    return AIPublicSettingsView(
        **base.model_dump(),
        saved_profiles=[_profile_public(p) for p in c.llm_profiles],
        active_profile_id=active,
        agent_llm=normalize_agent_llm(c.agent_llm),
    )


def _upsert_profile(c, name: str) -> None:
    name = name.strip()
    if not name:
        return
    snap = c.ai.model_copy(deep=True)
    for i, p in enumerate(c.llm_profiles):
        if p.name == name:
            c.llm_profiles[i] = LLMProfile(id=p.id, name=name, settings=snap)
            c.active_llm_profile_id = p.id
            return
    nid = str(uuid.uuid4())
    c.llm_profiles = [*c.llm_profiles, LLMProfile(id=nid, name=name, settings=snap)]
    c.active_llm_profile_id = nid


@router.get("", response_model=AIPublicSettingsView)
def get_ai() -> AIPublicSettingsView:
    c = load_config()
    return _to_view(c)


class AIUpdateBody(BaseModel):
    provider: Optional[AIProvider] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    headers: Optional[List[AIHeaderModel]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    openai_use_v1_prefix: Optional[bool] = None
    api_format: Optional[AIApiFormat] = None
    save_as_profile_name: Optional[str] = None
    agent_llm: Optional[Dict[str, AgentLLMBinding]] = None
    inherit_api_key_from_profile_id: Optional[str] = None


@router.put("", response_model=AIPublicSettingsView)
def put_ai(body: AIUpdateBody) -> AIPublicSettingsView:
    c = load_config()
    raw = body.model_dump(exclude_unset=True)
    save_name = raw.pop("save_as_profile_name", None)
    agent_llm_update = raw.pop("agent_llm", None)
    inherit_key_profile = raw.pop("inherit_api_key_from_profile_id", None)

    ai_fields = {
        "provider",
        "base_url",
        "api_key",
        "model",
        "headers",
        "temperature",
        "max_tokens",
        "openai_use_v1_prefix",
        "api_format",
    }
    ai_patch = {k: v for k, v in raw.items() if k in ai_fields}
    if ai_patch:
        d = c.ai.model_dump()
        d.update(ai_patch)
        c.ai = AISettings.model_validate(d)

    body_set = body.model_dump(exclude_unset=True)
    if inherit_key_profile:
        p = next((x for x in c.llm_profiles if x.id == inherit_key_profile), None)
        if p is None:
            raise HTTPException(
                404,
                "Profile not found for inherit_api_key_from_profile_id",
            ) from None
        key_set = "api_key" in body_set
        key_val = body_set.get("api_key")
        if not key_set or not (str(key_val) if key_val is not None else "").strip():
            c.ai = c.ai.model_copy(update={"api_key": p.settings.api_key or ""})

    if agent_llm_update is not None:
        alu = dict(agent_llm_update)
        if "job_hunt" in alu and "jobshunt" not in alu:
            alu["jobshunt"] = alu.pop("job_hunt")
        base = normalize_agent_llm(c.agent_llm)
        for k, v in alu.items():
            if k in KNOWN_AGENTS:
                base[k] = v
        c.agent_llm = base

    if save_name and str(save_name).strip():
        _upsert_profile(c, str(save_name).strip())
    _finalize_and_validate_bindings(c)
    save_config(c)
    return _to_view(load_config())


@router.get("/profiles/{profile_id}/editor", response_model=ProfileEditorView)
def get_profile_editor(profile_id: str) -> ProfileEditorView:
    c = load_config()
    p = next((x for x in c.llm_profiles if x.id == profile_id), None)
    if p is None:
        raise HTTPException(404, "Profile not found") from None
    pub = _to_public(p.settings)
    return ProfileEditorView(
        **pub.model_dump(),
        profile_id=p.id,
        profile_name=p.name,
    )


@router.post("/profiles/{profile_id}/activate", response_model=AIPublicSettingsView)
def activate_profile(profile_id: str) -> AIPublicSettingsView:
    c = load_config()
    p = next((x for x in c.llm_profiles if x.id == profile_id), None)
    if p is None:
        raise HTTPException(404, "Profile not found")
    c.ai = p.settings.model_copy(deep=True)
    c.active_llm_profile_id = profile_id
    _finalize_and_validate_bindings(c)
    save_config(c)
    return _to_view(load_config())


@router.delete("/profiles/{profile_id}", response_model=AIPublicSettingsView)
def delete_profile(profile_id: str) -> AIPublicSettingsView:
    c = load_config()
    c.llm_profiles = [p for p in c.llm_profiles if p.id != profile_id]
    if c.active_llm_profile_id == profile_id:
        c.active_llm_profile_id = None
    c.agent_llm = normalize_agent_llm(
        strip_bindings_for_deleted_profile(c.agent_llm, profile_id)
    )
    _finalize_and_validate_bindings(c)
    save_config(c)
    return _to_view(load_config())


@router.get("/models")
def list_models() -> Dict[str, Any]:
    c = load_config()
    a = c.ai
    if a.provider == "ollama":
        base = (a.base_url or "http://127.0.0.1:11434").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/api/tags"
        try:
            r = httpx.get(url, timeout=5.0)
            r.raise_for_status()
            data = r.json()
            return {"models": [m.get("name") for m in data.get("models", [])]}
        except Exception as e:
            return {"error": str(e), "models": []}
    if a.provider in ("openai", "openai_compatible") and a.api_format in (
        "responses",
        "path_chat",
        "auto",
    ):
        return {
            "models": [],
            "message": "This base URL has no standard model list; type the model name your gateway expects.",
        }
    if a.provider in ("openai", "openai_compatible", "openrouter"):
        from jobshunt.ai.openai_url import openai_api_root

        try:
            b = openai_api_root(a)
        except ValueError as e:
            return {"error": str(e), "models": []}
        base = merge_llm_request_headers(a)
        headers = {k: v for k, v in base.items() if k.lower() != "content-type"}
        try:
            r = httpx.get(
                f"{b}/models",
                headers=headers or None,
                timeout=10.0,
            )
            r.raise_for_status()
            d = r.json()
            return {"models": [m.get("id") for m in d.get("data", [])]}
        except Exception as e:
            return {"error": str(e), "models": []}
    if a.provider == "anthropic":
        return {
            "models": [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ],
        }
    return {"models": []}


@router.post("/test")
def test_connection() -> Dict[str, str]:
    c = load_config()
    a = c.ai
    if a.provider == "anthropic" and a.api_key:
        try:
            from anthropic import Anthropic

            cl = Anthropic(
                api_key=a.api_key,
                base_url=a.base_url or "https://api.anthropic.com",
            )
            cl.messages.create(
                model=a.model or "claude-3-5-haiku-20241022",
                max_tokens=8,
                messages=[{"role": "user", "content": "p"}],
            )
            return {"status": "ok", "message": "anthropic ok"}
        except Exception as e:
            raise HTTPException(400, str(e)) from e
    if a.provider == "anthropic" and not a.api_key:
        raise HTTPException(400, "Set Anthropic API key to test") from None

    if a.provider in ("openai", "openai_compatible") and a.api_format in (
        "responses",
        "path_chat",
        "auto",
    ):
        try:
            from jobshunt.ai.custom_path_api import test_custom_path

            msg, url_used = test_custom_path(c.ai)
        except Exception as e:
            raise HTTPException(400, str(e)) from e
        return {
            "status": "ok",
            "message": msg,
            "url_used": url_used,
        }

    from jobshunt.ai.openai_url import openai_api_root

    if a.provider == "ollama" and not a.base_url:
        a2 = a.model_copy(
            update={"base_url": "http://127.0.0.1:11434", "openai_use_v1_prefix": True}
        )
        b = openai_api_root(a2)
    else:
        try:
            b = openai_api_root(a)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    headers = merge_llm_request_headers(a)
    url_used = f"{b}/chat/completions"
    try:
        r = httpx.post(
            url_used,
            headers=headers,
            json={
                "model": a.model,
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 16,
            },
            timeout=45.0,
        )
        if r.status_code >= 400:
            snippet = (r.text or "").strip().replace("\n", " ")[:900]
            hint = ""
            if r.status_code == 429 and a.provider == "openrouter":
                low = snippet.lower()
                if "rate-limited upstream" in low or (
                    ":free" in snippet and "provider returned error" in low
                ):
                    hint = (
                        " This is usually shared upstream throttling on a `:free` model, not your OpenRouter "
                        "balance. Use a paid or non-`:free` model id, wait and retry, or add your own provider key "
                        "under OpenRouter → Settings → Integrations (BYOK) so limits accrue to you. "
                        "See https://openrouter.ai/settings/integrations"
                    )
                else:
                    hint = (
                        " OpenRouter 429: rate limits, model-specific caps, or edge rules. "
                        "Check https://openrouter.ai/settings/keys and credits; try another model."
                    )
            raise HTTPException(
                400,
                f"HTTP {r.status_code} from LLM{f': {snippet}' if snippet else ''}. "
                f"(tried: {url_used}){hint}",
            )
        return {
            "status": "ok",
            "message": "Chat completion test succeeded",
            "url_used": url_used,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"{e!s}  (tried: {url_used})") from e
