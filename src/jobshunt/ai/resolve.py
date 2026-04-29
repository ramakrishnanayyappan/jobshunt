"""Resolve which AISettings apply for a given JobShunt agent."""
from __future__ import annotations

from typing import Dict, List, Optional

from jobshunt.ai.constants import KNOWN_AGENTS
from jobshunt.config import load_config
from jobshunt.models import AISettings, AgentLLMBinding


class AgentLLMNotConfigured(RuntimeError):
    """Raised when an agent has no valid primary saved profile (and optional fallbacks)."""

    def __init__(self, agent: str, detail: Optional[str] = None):
        self.agent = agent
        self.detail = (
            detail
            or f"No primary saved model for agent '{agent}'. Set one under Settings → Agent models."
        )
        super().__init__(self.detail)


def _profile_settings(profile_id: Optional[str]) -> Optional[AISettings]:
    if not profile_id:
        return None
    c = load_config()
    for p in c.llm_profiles:
        if p.id == profile_id:
            return p.settings.model_copy(deep=True)
    return None


def resolve_ai_settings(agent: Optional[str] = None) -> AISettings:
    """Return settings for ad-hoc / non-agent use from global `config.ai`.

    For `jobshunt`, only saved-profile bindings are used — global `ai` is not a fallback when the primary is unset.
    """
    c = load_config()
    if not agent or agent not in KNOWN_AGENTS:
        return c.ai.model_copy(deep=True)
    raw = c.agent_llm.get(agent)
    if not raw:
        raise AgentLLMNotConfigured(agent)
    pid = (raw.primary_profile_id or "").strip()
    st = _profile_settings(pid if pid else None)
    if st is None:
        raise AgentLLMNotConfigured(agent)
    return st


def resolve_llm_chain(agent: Optional[str]) -> List[AISettings]:
    """Ordered settings to try: primary, then each fallback profile (no duplicates)."""
    c = load_config()
    if not agent or agent not in KNOWN_AGENTS:
        return [c.ai.model_copy(deep=True)]
    primary = resolve_ai_settings(agent)
    chain: List[AISettings] = [primary]
    raw = c.agent_llm.get(agent)
    if not raw:
        return chain
    primary_id = (raw.primary_profile_id or "").strip() or None
    seen_ids = {primary_id} if primary_id else set()
    for fid in raw.fallback_profile_ids or []:
        if not fid or fid in seen_ids:
            continue
        seen_ids.add(fid)
        st = _profile_settings(fid)
        if st:
            chain.append(st)
    return chain


def normalize_agent_llm(data: Dict[str, AgentLLMBinding]) -> Dict[str, AgentLLMBinding]:
    out: Dict[str, AgentLLMBinding] = {k: AgentLLMBinding() for k in sorted(KNOWN_AGENTS)}
    for k, v in data.items():
        if k in KNOWN_AGENTS:
            out[k] = v
    return out


def strip_bindings_for_deleted_profile(
    bindings: Dict[str, AgentLLMBinding], deleted_id: str
) -> Dict[str, AgentLLMBinding]:
    out = dict(bindings)
    for key in KNOWN_AGENTS:
        b = out.get(key) or AgentLLMBinding()
        pp = b.primary_profile_id if b.primary_profile_id != deleted_id else None
        ff = [x for x in (b.fallback_profile_ids or []) if x != deleted_id]
        out[key] = AgentLLMBinding(primary_profile_id=pp, fallback_profile_ids=ff)
    return out
