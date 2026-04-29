"""Multi-workspace registry — each workspace has isolated pipeline, vault summary, runs, batch, story bank."""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from jobshunt.config import load_config
from jobshunt.models import JobShuntSettings
from jobshunt.paths import data_root


def jobshunt_root() -> Path:
    modern = data_root() / "jobshunt"
    legacy = data_root() / "job_hunt"
    if modern.exists():
        p = modern
    elif legacy.exists():
        p = legacy
    else:
        p = modern
        p.mkdir(parents=True, exist_ok=True)
        return p
    p.mkdir(parents=True, exist_ok=True)
    return p


def workspaces_root() -> Path:
    p = jobshunt_root() / "workspaces"
    p.mkdir(parents=True, exist_ok=True)
    return p


def workspace_data_dir(workspace_id: str) -> Path:
    d = workspaces_root() / workspace_id
    d.mkdir(parents=True, exist_ok=True)
    return d


REGISTRY_NAME = "workspaces_registry.json"


def registry_path() -> Path:
    return jobshunt_root() / REGISTRY_NAME


_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _normalize_id(raw: str) -> str:
    s = (raw or "").strip()
    if _ID_RE.match(s):
        return s
    raise ValueError("Invalid workspace id: use letters, numbers, underscore, hyphen (max 64).")


class WorkspaceRecord(BaseModel):
    id: str
    name: str = "Workspace"
    """Optional vault path; empty string means use global jobshunt.resume_vault_path."""
    resume_vault_path: str = ""
    """Optional explicit vault summary file; empty means workspaces/<id>/vault_summary.txt."""
    vault_summary_path: str = ""
    user_preferences: List[str] = Field(default_factory=list)
    archetype_hints: List[str] = Field(default_factory=list)


class WorkspacesRegistry(BaseModel):
    active_id: str = "default"
    workspaces: List[WorkspaceRecord] = Field(
        default_factory=lambda: [WorkspaceRecord(id="default", name="Default")]
    )


def load_registry() -> WorkspacesRegistry:
    migrate_legacy_if_needed()
    p = registry_path()
    if not p.is_file():
        reg = WorkspacesRegistry()
        save_registry(reg)
        return reg
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        reg = WorkspacesRegistry()
        save_registry(reg)
        return reg
    try:
        return WorkspacesRegistry.model_validate(raw)
    except Exception:
        reg = WorkspacesRegistry()
        save_registry(reg)
        return reg


def save_registry(reg: WorkspacesRegistry) -> None:
    reg = reg.model_copy()
    ids = [w.id for w in reg.workspaces]
    if reg.active_id not in ids and reg.workspaces:
        reg = reg.model_copy(update={"active_id": reg.workspaces[0].id})
    p = registry_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(reg.model_dump(), f, indent=2, ensure_ascii=False)
    for w in reg.workspaces:
        workspace_data_dir(w.id)


_migrate_done = False


def migrate_legacy_if_needed() -> None:
    """Move pre-workspace files into workspaces/default/ once."""
    global _migrate_done
    if _migrate_done:
        return
    if registry_path().is_file():
        _migrate_done = True
        return
    _migrate_done = True
    root = jobshunt_root()
    ws_dir = workspace_data_dir("default")
    legacy_files = [
        "pipeline.json",
        "story_bank.json",
        "vault_summary_manifest.json",
        "vault_summary.txt",
        "vault_summary_changelog.jsonl",
    ]
    for name in legacy_files:
        src = root / name
        if src.is_file():
            dest = ws_dir / name
            if not dest.exists():
                shutil.move(str(src), str(dest))
    for dname in ("runs", "batch"):
        src = root / dname
        if src.is_dir() and any(src.iterdir()):
            dest = ws_dir / dname
            if not dest.exists():
                shutil.move(str(src), str(dest))
    cfg = load_config()
    reg = WorkspacesRegistry(
        active_id="default",
        workspaces=[
            WorkspaceRecord(
                id="default",
                name="Default",
                user_preferences=list(cfg.jobshunt.user_preferences or []),
                archetype_hints=list(cfg.jobshunt.archetype_hints or []),
                vault_summary_path=(cfg.jobshunt.vault_summary_path or "").strip(),
            )
        ],
    )
    save_registry(reg)


def get_workspace(workspace_id: str) -> Optional[WorkspaceRecord]:
    wid = (workspace_id or "").strip()
    for w in load_registry().workspaces:
        if w.id == wid:
            return w
    return None


def require_workspace(workspace_id: str) -> WorkspaceRecord:
    w = get_workspace((workspace_id or "").strip())
    if not w:
        raise KeyError(f"Unknown workspace: {workspace_id!r}")
    return w


def resolve_workspace_id(query_workspace: Optional[str]) -> str:
    reg = load_registry()
    q = (query_workspace or "").strip()
    if q:
        if not get_workspace(q):
            raise KeyError(f"Unknown workspace: {q!r}")
        return q
    return reg.active_id


def set_active_workspace(workspace_id: str) -> WorkspacesRegistry:
    require_workspace(workspace_id)
    reg = load_registry()
    reg = reg.model_copy(update={"active_id": workspace_id})
    save_registry(reg)
    return reg


def effective_vault_path(ws: WorkspaceRecord, global_cfg: JobShuntSettings) -> Path:
    raw = (ws.resume_vault_path or "").strip()
    if not raw:
        raw = global_cfg.resume_vault_path or "~/Documents/resumes"
    return Path(raw).expanduser()


def effective_jobshunt_settings(ws: WorkspaceRecord, global_cfg: JobShuntSettings) -> JobShuntSettings:
    """Merge workspace-specific paths and preference lists with global Job Hunt settings."""
    vsp = (ws.vault_summary_path or "").strip() or (global_cfg.vault_summary_path or "").strip()
    return global_cfg.model_copy(
        update={
            "vault_summary_path": vsp,
            "user_preferences": list(ws.user_preferences or []),
            "archetype_hints": list(ws.archetype_hints or []),
        }
    )


def create_workspace(*, name: str, resume_vault_path: str = "") -> WorkspaceRecord:
    reg = load_registry()
    nid = uuid.uuid4().hex[:12]
    w = WorkspaceRecord(
        id=nid,
        name=(name or "Workspace").strip()[:120] or "Workspace",
        resume_vault_path=(resume_vault_path or "").strip(),
    )
    reg = reg.model_copy(update={"workspaces": [*reg.workspaces, w]})
    save_registry(reg)
    workspace_data_dir(nid)
    return w


def update_workspace(
    workspace_id: str,
    *,
    name: Optional[str] = None,
    resume_vault_path: Optional[str] = None,
    vault_summary_path: Optional[str] = None,
    user_preferences: Optional[List[str]] = None,
    archetype_hints: Optional[List[str]] = None,
) -> WorkspaceRecord:
    require_workspace(workspace_id)
    reg = load_registry()
    out: Optional[WorkspaceRecord] = None
    new_list: List[WorkspaceRecord] = []
    for w in reg.workspaces:
        if w.id != workspace_id:
            new_list.append(w)
            continue
        patch: Dict[str, Any] = {}
        if name is not None:
            patch["name"] = (name or "").strip()[:120] or w.name
        if resume_vault_path is not None:
            patch["resume_vault_path"] = (resume_vault_path or "").strip()
        if vault_summary_path is not None:
            patch["vault_summary_path"] = (vault_summary_path or "").strip()
        if user_preferences is not None:
            patch["user_preferences"] = list(user_preferences or [])
        if archetype_hints is not None:
            patch["archetype_hints"] = list(archetype_hints or [])
        nw = w.model_copy(update=patch)
        new_list.append(nw)
        out = nw
    if out is None:
        raise KeyError(workspace_id)
    reg = reg.model_copy(update={"workspaces": new_list})
    save_registry(reg)
    return out


def delete_workspace(workspace_id: str) -> None:
    reg = load_registry()
    if len(reg.workspaces) <= 1:
        raise ValueError("Cannot delete the last workspace.")
    Wid = (workspace_id or "").strip()
    if Wid == reg.active_id:
        raise ValueError("Switch active workspace before deleting this one.")
    new_ws = [w for w in reg.workspaces if w.id != Wid]
    if len(new_ws) == len(reg.workspaces):
        raise KeyError(Wid)
    reg = reg.model_copy(update={"workspaces": new_ws})
    save_registry(reg)
    d = workspaces_root() / Wid
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


def registry_public_dict(reg: WorkspacesRegistry) -> Dict[str, Any]:
    return {
        "active_id": reg.active_id,
        "workspaces": [
            {
                "id": w.id,
                "name": w.name,
                "resume_vault_path": w.resume_vault_path,
                "vault_summary_path": w.vault_summary_path,
            }
            for w in reg.workspaces
        ],
    }
