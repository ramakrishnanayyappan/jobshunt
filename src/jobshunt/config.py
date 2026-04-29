from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from jobshunt.ai.constants import KNOWN_AGENTS
from jobshunt.models import AgentLLMBinding, AISettings, JobShuntAppConfig
from jobshunt.paths import config_path


def _default_config_path(override: Optional[Path] = None) -> Path:
    return override or config_path()


def _migrate_raw_config(raw: Dict[str, Any]) -> None:
    """Accept legacy YAML keys (`job_hunt`, agent_llm.job_hunt) after top-level rename to jobshunt."""
    if not isinstance(raw, dict):
        return
    if "job_hunt" in raw and "jobshunt" not in raw:
        raw["jobshunt"] = raw.pop("job_hunt")
    al = raw.get("agent_llm")
    if isinstance(al, dict) and "job_hunt" in al and "jobshunt" not in al:
        al["jobshunt"] = al.pop("job_hunt")


def apply_agent_llm_defaults(cfg: JobShuntAppConfig) -> None:
    known = {p.id for p in cfg.llm_profiles}
    merged: Dict[str, AgentLLMBinding] = {k: AgentLLMBinding() for k in sorted(KNOWN_AGENTS)}
    for k, v in (cfg.agent_llm or {}).items():
        if k in merged:
            merged[k] = v
    active = cfg.active_llm_profile_id
    for agent in KNOWN_AGENTS:
        b = merged[agent]
        pid = (b.primary_profile_id or "").strip()
        if pid in known:
            continue
        b = b.model_copy(update={"primary_profile_id": None})
        merged[agent] = b
        new_pid: Optional[str] = None
        if active and active in known:
            new_pid = active
        elif len(cfg.llm_profiles) == 1:
            new_pid = cfg.llm_profiles[0].id
        if new_pid:
            merged[agent] = b.model_copy(update={"primary_profile_id": new_pid})
    cfg.agent_llm = merged


def load_config(path: Optional[Path] = None) -> JobShuntAppConfig:
    p = _default_config_path(path)
    if not p.exists():
        cfg = JobShuntAppConfig()
        b = AISettings.from_env_bootstrap()
        if b.api_key or os.environ.get("OPENAI_BASE_URL") or os.environ.get("ANTHROPIC_API_KEY"):
            cfg.ai = b
        apply_agent_llm_defaults(cfg)
        return cfg
    with open(p, "r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f) or {}
    _migrate_raw_config(raw)
    cfg = JobShuntAppConfig.model_validate(raw)
    apply_agent_llm_defaults(cfg)
    return cfg


def save_config(cfg: JobShuntAppConfig, path: Optional[Path] = None) -> None:
    p = _default_config_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(
            cfg.model_dump(mode="python", by_alias=True),
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
