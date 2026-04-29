"""Per-agent LLM resolution (no global fallback for agents)."""
from __future__ import annotations

import pytest

from jobshunt.ai.resolve import (
    AgentLLMNotConfigured,
    normalize_agent_llm,
    resolve_ai_settings,
    resolve_llm_chain,
)
from jobshunt.models import AISettings, AgentLLMBinding, JobShuntAppConfig, LLMProfile


def test_agent_requires_primary(monkeypatch: pytest.MonkeyPatch):
    c = JobShuntAppConfig()
    c.llm_profiles = [
        LLMProfile(id="p1", name="one", settings=AISettings(model="mono")),
    ]
    c.agent_llm = normalize_agent_llm(
        {
            "jobshunt": AgentLLMBinding(primary_profile_id=None),
        }
    )
    monkeypatch.setattr("jobshunt.ai.resolve.load_config", lambda: c)
    with pytest.raises(AgentLLMNotConfigured):
        resolve_ai_settings("jobshunt")

    c_ok = JobShuntAppConfig()
    c_ok.llm_profiles = c.llm_profiles
    c_ok.agent_llm = normalize_agent_llm(
        {"jobshunt": AgentLLMBinding(primary_profile_id="p1")}
    )
    monkeypatch.setattr("jobshunt.ai.resolve.load_config", lambda: c_ok)
    resolve_ai_settings("jobshunt")


def test_agent_uses_saved_profile_not_global(monkeypatch: pytest.MonkeyPatch):
    c = JobShuntAppConfig()
    c.ai = AISettings(provider="openai", model="global-only")
    prof = AISettings(provider="openrouter", base_url="https://openrouter.ai/api/v1", model="orf")
    c.llm_profiles = [LLMProfile(id="or1", name="OR", settings=prof)]
    c.agent_llm = normalize_agent_llm({"jobshunt": AgentLLMBinding(primary_profile_id="or1")})
    monkeypatch.setattr("jobshunt.ai.resolve.load_config", lambda: c)
    st = resolve_ai_settings("jobshunt")
    assert st.model == "orf"
    assert st.provider == "openrouter"


def test_non_agent_uses_global_ai(monkeypatch: pytest.MonkeyPatch):
    c = JobShuntAppConfig()
    c.ai = AISettings(model="from-global")
    monkeypatch.setattr("jobshunt.ai.resolve.load_config", lambda: c)
    st = resolve_ai_settings(None)
    assert st.model == "from-global"


def test_chain_includes_fallback(monkeypatch: pytest.MonkeyPatch):
    c = JobShuntAppConfig()
    c.llm_profiles = [
        LLMProfile(id="a", name="A", settings=AISettings(model="ma")),
        LLMProfile(id="b", name="B", settings=AISettings(model="mb")),
    ]
    c.agent_llm = normalize_agent_llm(
        {
            "jobshunt": AgentLLMBinding(primary_profile_id="a", fallback_profile_ids=["b"]),
        }
    )
    monkeypatch.setattr("jobshunt.ai.resolve.load_config", lambda: c)
    chain = resolve_llm_chain("jobshunt")
    assert [x.model for x in chain] == ["ma", "mb"]
