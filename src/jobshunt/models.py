from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator

AIProvider = Literal["openai", "anthropic", "ollama", "openai_compatible", "openrouter"]
AIApiFormat = Literal["openai", "responses", "path_chat", "auto"]


class AIHeaderModel(BaseModel):
    name: str = ""
    value: str = ""


class AISettings(BaseModel):
    provider: AIProvider = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    headers: List[AIHeaderModel] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    openai_use_v1_prefix: bool = True
    api_format: AIApiFormat = "openai"

    @classmethod
    def from_env_bootstrap(cls) -> "AISettings":
        import os

        s = cls()
        if os.environ.get("OPENAI_API_KEY"):
            s.provider = "openai"
            s.api_key = os.environ.get("OPENAI_API_KEY", "")
            s.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if os.environ.get("ANTHROPIC_API_KEY"):
            s.provider = "anthropic"
            s.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            s.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        if os.environ.get("OPENROUTER_API_KEY"):
            s.provider = "openrouter"
            s.api_key = os.environ.get("OPENROUTER_API_KEY", "")
            s.base_url = os.environ.get(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            )
        return s


class LLMProfile(BaseModel):
    id: str
    name: str
    settings: AISettings


class HttpSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    static_dir: Optional[str] = None


class JobShuntSettings(BaseModel):
    """Résumé vault + output paths."""

    resume_vault_path: str = "~/Documents/resumes"
    output_path: str = ""
    max_vault_chars: int = 80_000
    max_vault_files: int = 40
    display_name_title_case: bool = True
    apply_helper_script: str = ""
    allow_apply_subprocess: bool = False
    user_preferences: List[str] = Field(default_factory=list)
    archetype_hints: List[str] = Field(default_factory=list)
    evaluation_dimension_weights: Dict[str, float] = Field(default_factory=dict)
    use_story_bank_in_draft: bool = False
    scout_enabled: bool = False
    use_vault_summary_for_context: bool = False
    vault_summary_path: str = ""
    block_draft_when_vault_summary_stale: bool = True
    auto_refine_after_draft: bool = False


class AgentLLMBinding(BaseModel):
    primary_profile_id: Optional[str] = None
    fallback_profile_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_single_fallback(cls, data: Any) -> Any:
        if isinstance(data, dict) and "fallback_profile_id" in data:
            has_list = "fallback_profile_ids" in data
            legacy = data.get("fallback_profile_id")
            data = {k: v for k, v in data.items() if k != "fallback_profile_id"}
            if not has_list:
                data["fallback_profile_ids"] = [legacy] if legacy else []
        return data


def _default_agent_llm() -> Dict[str, AgentLLMBinding]:
    return {"jobshunt": AgentLLMBinding()}


class JobShuntAppConfig(BaseModel):
    """App configuration persisted to YAML (no secrets ship in-repo — user creates locally)."""

    jobshunt: JobShuntSettings = Field(
        default_factory=JobShuntSettings,
        validation_alias=AliasChoices("jobshunt", "job_hunt"),
        serialization_alias="jobshunt",
    )
    ai: AISettings = Field(default_factory=AISettings)
    agent_llm: Dict[str, AgentLLMBinding] = Field(default_factory=_default_agent_llm)
    llm_profiles: List[LLMProfile] = Field(default_factory=list)
    active_llm_profile_id: Optional[str] = None
    http: HttpSettings = Field(default_factory=HttpSettings)


class AIPublicSettings(BaseModel):
    provider: AIProvider
    base_url: str
    has_api_key: bool
    model: str
    headers: List[AIHeaderModel]
    temperature: float
    max_tokens: int
    openai_use_v1_prefix: bool
    api_format: AIApiFormat


class ProfileEditorView(AIPublicSettings):
    profile_id: str
    profile_name: str


class LLMProfilePublic(BaseModel):
    id: str
    name: str
    provider: AIProvider
    model: str
    api_format: AIApiFormat
    base_url: str
    has_api_key: bool


class AIPublicSettingsView(AIPublicSettings):
    saved_profiles: List[LLMProfilePublic] = Field(default_factory=list)
    active_profile_id: Optional[str] = None
    agent_llm: Dict[str, AgentLLMBinding] = Field(default_factory=_default_agent_llm)
