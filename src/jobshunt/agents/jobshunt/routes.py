from __future__ import annotations

import re

import httpx
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from jobshunt.config import load_config, save_config
from jobshunt.models import JobShuntSettings
from . import evaluation, insights, negotiate, pipeline, scout, story_bank, workspaces as ws_mod
from . import job_spec as job_spec_mod
from . import batch_jobs, render, resume_vault, tailor, validate, vault_summary
from . import insight_apply, jobshunt_chat, preferences_from_summary, resume_refine, store


router = APIRouter(prefix="/api/agents/jobshunt", tags=["jobshunt"])


def workspace_id_dep(workspace_id: Optional[str] = Query(None, alias="workspace_id")) -> str:
    try:
        return ws_mod.resolve_workspace_id(workspace_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


def _output_base(cfg: JobShuntSettings) -> Path:
    p = (cfg.output_path or "").strip()
    if p:
        return Path(p).expanduser().resolve()
    return (ws_mod.jobshunt_root() / "exports").resolve()


def _path_display(path: str) -> str:
    path = path.rstrip("/")
    home = str(Path.home())
    if path.startswith(home + "/") or path == home:
        return "~" + path[len(home) :] if path != home else "~"
    return path


def _run_osascript(script: str) -> str:
    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip() or "cancelled or denied"
        low = err.lower()
        if "-128" in err or "user canceled" in low:
            return ""
        raise HTTPException(400, err)
    return (r.stdout or "").strip()


def _slug(text: str, basename: Optional[str]) -> str:
    if basename and basename.strip():
        s = re.sub(r"[^a-zA-Z0-9._-]+", "_", basename.strip())[:80]
        s = s.strip("._-")
        return s or "resume"
    line0 = text.split("\n", 1)[0].strip()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", line0)[:60]
    s = s.strip("_")
    return s or "resume"


@router.get("/status")
def status(workspace_id: str = Depends(workspace_id_dep)) -> Dict[str, Any]:
    ws = ws_mod.require_workspace(workspace_id)
    global_cfg = load_config().jobshunt
    cfg = ws_mod.effective_jobshunt_settings(ws, global_cfg)
    vault = ws_mod.effective_vault_path(ws, global_cfg)
    vres = vault.expanduser().resolve() if vault.expanduser().exists() else vault.expanduser()
    exists = vres.exists()
    is_file = exists and vres.is_file()
    is_dir = exists and vres.is_dir()
    if is_file:
        kind = "file"
    elif is_dir:
        kind = "folder"
    else:
        kind = "missing"
    out = _output_base(global_cfg)
    sources = resume_vault.list_vault_sources(vault)
    reg = ws_mod.load_registry()
    return {
        "workspace_id": ws.id,
        "workspace_name": ws.name,
        "workspace_resume_vault_path": ws.resume_vault_path,
        "workspace_vault_summary_path": ws.vault_summary_path,
        "global_default_vault_path": str(Path(global_cfg.resume_vault_path).expanduser()),
        "active_workspace_id": reg.active_id,
        "workspaces": [
            {"id": w.id, "name": w.name, "resume_vault_path": w.resume_vault_path}
            for w in reg.workspaces
        ],
        "resume_vault_path": str(vault),
        "resume_vault_path_display": _path_display(str(vres)) if exists else str(vault),
        "vault_exists": exists,
        "vault_kind": kind,
        "output_path": str(out),
        "output_path_display": _path_display(str(out)),
        "output_path_configured": bool((global_cfg.output_path or "").strip()),
        "vault_preview_files": [p.name for p in sources[:15]],
        "vault_source_count": len(sources),
        "apply_helper_configured": bool(global_cfg.apply_helper_script.strip()),
        "allow_apply_subprocess": global_cfg.allow_apply_subprocess,
        "use_story_bank_in_draft": global_cfg.use_story_bank_in_draft,
        "scout_enabled": global_cfg.scout_enabled,
        "user_preferences": list(ws.user_preferences or []),
        "archetype_hints": list(ws.archetype_hints or []),
        "evaluation_dimension_weights": dict(global_cfg.evaluation_dimension_weights or {}),
        "auto_refine_after_draft": global_cfg.auto_refine_after_draft,
        **vault_summary.status_payload(vault, cfg, workspace_id),
    }


class JobShuntPathsBody(BaseModel):
    resume_vault_path: Optional[str] = None
    output_path: Optional[str] = None
    user_preferences: Optional[List[str]] = None
    archetype_hints: Optional[List[str]] = None
    evaluation_dimension_weights: Optional[Dict[str, float]] = None
    use_story_bank_in_draft: Optional[bool] = None
    scout_enabled: Optional[bool] = None
    use_vault_summary_for_context: Optional[bool] = None
    vault_summary_path: Optional[str] = None
    block_draft_when_vault_summary_stale: Optional[bool] = None
    auto_refine_after_draft: Optional[bool] = None


@router.put("/settings")
def put_settings(
    body: JobShuntPathsBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    c = load_config()
    oh = c.jobshunt
    data = body.model_dump(exclude_unset=True)
    if "resume_vault_path" in data:
        raw = (data["resume_vault_path"] or "").strip()
        ws_mod.update_workspace(workspace_id, resume_vault_path=raw)
    if "output_path" in data:
        oh = oh.model_copy(update={"output_path": (data["output_path"] or "").strip()})
    if "user_preferences" in data and data["user_preferences"] is not None:
        ws_mod.update_workspace(
            workspace_id, user_preferences=list(data["user_preferences"] or [])
        )
    if "archetype_hints" in data and data["archetype_hints"] is not None:
        ws_mod.update_workspace(
            workspace_id, archetype_hints=list(data["archetype_hints"] or [])
        )
    if "evaluation_dimension_weights" in data and data["evaluation_dimension_weights"] is not None:
        oh = oh.model_copy(
            update={"evaluation_dimension_weights": dict(data["evaluation_dimension_weights"] or {})}
        )
    if "use_story_bank_in_draft" in data and data["use_story_bank_in_draft"] is not None:
        oh = oh.model_copy(update={"use_story_bank_in_draft": bool(data["use_story_bank_in_draft"])})
    if "scout_enabled" in data and data["scout_enabled"] is not None:
        oh = oh.model_copy(update={"scout_enabled": bool(data["scout_enabled"])})
    if "use_vault_summary_for_context" in data and data["use_vault_summary_for_context"] is not None:
        oh = oh.model_copy(
            update={"use_vault_summary_for_context": bool(data["use_vault_summary_for_context"])}
        )
    if "vault_summary_path" in data and data["vault_summary_path"] is not None:
        ws_mod.update_workspace(
            workspace_id,
            vault_summary_path=(data["vault_summary_path"] or "").strip(),
        )
    if "block_draft_when_vault_summary_stale" in data and data["block_draft_when_vault_summary_stale"] is not None:
        oh = oh.model_copy(
            update={
                "block_draft_when_vault_summary_stale": bool(
                    data["block_draft_when_vault_summary_stale"]
                )
            }
        )
    if "auto_refine_after_draft" in data and data["auto_refine_after_draft"] is not None:
        oh = oh.model_copy(
            update={"auto_refine_after_draft": bool(data["auto_refine_after_draft"])}
        )
    c = c.model_copy(update={"jobshunt": oh})
    save_config(c)
    return status(workspace_id)


@router.get("/pick-vault-folder")
def pick_vault_folder() -> Dict[str, Any]:
    if sys.platform != "darwin":
        raise HTTPException(
            501,
            "Folder picker is only available on macOS. Set the path in config or type it in Job hunt settings.",
        )
    script = """
tell application "Finder" to activate
delay 0.2
return POSIX path of (choose folder with prompt "Job Hunt — résumé vault folder (all résumés inside will be used)" default location (path to home folder))
"""
    raw = _run_osascript(script)
    if not raw:
        return {"cancelled": True}
    path = raw.rstrip().rstrip("/")
    return {"path": path, "path_display": _path_display(path)}


@router.get("/pick-vault-file")
def pick_vault_file() -> Dict[str, Any]:
    if sys.platform != "darwin":
        raise HTTPException(
            501,
            "File picker is only available on macOS. Set the path in config or type the full path.",
        )
    script = """
tell application "Finder" to activate
delay 0.2
return POSIX path of (choose file with prompt "Job Hunt — select one résumé (.txt, .md, .docx, .pdf)" default location (path to documents folder))
"""
    raw = _run_osascript(script)
    if not raw:
        return {"cancelled": True}
    path = raw.rstrip()
    return {"path": path, "path_display": _path_display(path)}


@router.get("/pick-output-folder")
def pick_output_folder() -> Dict[str, Any]:
    if sys.platform != "darwin":
        raise HTTPException(
            501,
            "Folder picker is only available on macOS. Type an output path in config if needed.",
        )
    script = """
tell application "Finder" to activate
delay 0.2
return POSIX path of (choose folder with prompt "Job Hunt — where to keep exports / run metadata hint" default location (path to home folder))
"""
    raw = _run_osascript(script)
    if not raw:
        return {"cancelled": True}
    path = raw.rstrip().rstrip("/")
    return {"path": path, "path_display": _path_display(path)}


class CreateWorkspaceBody(BaseModel):
    name: str = "New workspace"
    resume_vault_path: str = ""


class RenameWorkspaceBody(BaseModel):
    name: str


class ActiveWorkspaceBody(BaseModel):
    workspace_id: str


@router.get("/workspaces")
def list_workspaces_route() -> Dict[str, Any]:
    reg = ws_mod.load_registry()
    return ws_mod.registry_public_dict(reg)


@router.post("/workspaces")
def create_workspace_route(body: CreateWorkspaceBody) -> Dict[str, Any]:
    w = ws_mod.create_workspace(
        name=body.name,
        resume_vault_path=(body.resume_vault_path or "").strip(),
    )
    reg = ws_mod.set_active_workspace(w.id)
    return {"workspace": {"id": w.id, "name": w.name}, **ws_mod.registry_public_dict(reg)}


@router.put("/workspaces/active")
def set_active_workspace_route(body: ActiveWorkspaceBody) -> Dict[str, Any]:
    reg = ws_mod.set_active_workspace(body.workspace_id)
    return ws_mod.registry_public_dict(reg)


@router.put("/workspaces/{ws_id}")
def update_workspace_route(ws_id: str, body: JobShuntPathsBody) -> Dict[str, Any]:
    ws_mod.require_workspace(ws_id)
    data = body.model_dump(exclude_unset=True)
    if "resume_vault_path" in data:
        ws_mod.update_workspace(
            ws_id, resume_vault_path=(data["resume_vault_path"] or "").strip()
        )
    if "vault_summary_path" in data:
        ws_mod.update_workspace(
            ws_id, vault_summary_path=(data["vault_summary_path"] or "").strip()
        )
    if "user_preferences" in data and data["user_preferences"] is not None:
        ws_mod.update_workspace(
            ws_id, user_preferences=list(data["user_preferences"] or [])
        )
    if "archetype_hints" in data and data["archetype_hints"] is not None:
        ws_mod.update_workspace(ws_id, archetype_hints=list(data["archetype_hints"] or []))
    return status(ws_id)


@router.put("/workspaces/{ws_id}/rename")
def rename_workspace_route(ws_id: str, body: RenameWorkspaceBody) -> Dict[str, Any]:
    ws_mod.update_workspace(ws_id, name=body.name)
    reg = ws_mod.load_registry()
    return ws_mod.registry_public_dict(reg)


@router.delete("/workspaces/{ws_id}")
def delete_workspace_route(ws_id: str) -> Dict[str, Any]:
    try:
        ws_mod.delete_workspace(ws_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    reg = ws_mod.load_registry()
    return ws_mod.registry_public_dict(reg)


@router.post("/workspaces/{ws_id}/generate-preferences")
def generate_preferences_route(ws_id: str) -> Dict[str, Any]:
    ws_mod.require_workspace(ws_id)
    global_cfg = load_config().jobshunt
    cfg = ws_mod.effective_jobshunt_settings(ws_mod.require_workspace(ws_id), global_cfg)
    sp = vault_summary.summary_file_path(cfg, ws_id)
    text = vault_summary.read_summary_text(sp)
    if not text.strip():
        raise HTTPException(
            400,
            "Vault summary is empty. Rebuild or update the vault summary for this workspace first.",
        )
    try:
        prefs, hints = preferences_from_summary.generate_preferences_from_summary(text)
    except Exception as e:
        raise HTTPException(502, str(e)) from e
    ws_mod.update_workspace(ws_id, user_preferences=prefs, archetype_hints=hints)
    return {"user_preferences": prefs, "archetype_hints": hints}


@router.get("/vault-summary/status")
def vault_summary_status_route(workspace_id: str = Depends(workspace_id_dep)) -> Dict[str, Any]:
    ws = ws_mod.require_workspace(workspace_id)
    global_cfg = load_config().jobshunt
    cfg = ws_mod.effective_jobshunt_settings(ws, global_cfg)
    vault = ws_mod.effective_vault_path(ws, global_cfg)
    return vault_summary.status_payload(vault, cfg, workspace_id)


@router.get("/vault-summary/preview")
def vault_summary_preview(
    limit: int = 12_000,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    ws = ws_mod.require_workspace(workspace_id)
    cfg = ws_mod.effective_jobshunt_settings(ws, load_config().jobshunt)
    sp = vault_summary.summary_file_path(cfg, workspace_id)
    t = vault_summary.read_summary_text(sp)
    lim = max(200, min(limit, 80_000))
    return {"path": str(sp), "text": t[:lim], "truncated": len(t) > lim, "total_chars": len(t)}


class VaultRescanBody(BaseModel):
    only_pending: bool = True
    paths: Optional[List[str]] = None


@router.post("/vault-summary/rescan")
def vault_summary_rescan(
    body: VaultRescanBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    ws = ws_mod.require_workspace(workspace_id)
    global_cfg = load_config().jobshunt
    cfg = ws_mod.effective_jobshunt_settings(ws, global_cfg)
    vault = ws_mod.effective_vault_path(ws, global_cfg)
    try:
        return vault_summary.merge_pending(
            vault,
            cfg,
            workspace_id,
            only_pending=body.only_pending,
            paths_filter=body.paths,
        )
    except ImportError as e:
        raise HTTPException(501, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            502,
            "Vault summary merge could not reach the LLM. Check AI settings and network. "
            f"Detail: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(502, str(e)) from e


@router.post("/vault-summary/rebuild")
def vault_summary_rebuild(workspace_id: str = Depends(workspace_id_dep)) -> Dict[str, Any]:
    ws = ws_mod.require_workspace(workspace_id)
    global_cfg = load_config().jobshunt
    cfg = ws_mod.effective_jobshunt_settings(ws, global_cfg)
    vault = ws_mod.effective_vault_path(ws, global_cfg)
    try:
        return vault_summary.rebuild_from_vault(vault, cfg, workspace_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except ImportError as e:
        raise HTTPException(501, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            502,
            "Vault summary rebuild could not reach the LLM. Check AI settings and network. "
            f"Detail: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(502, str(e)) from e


class DraftBody(BaseModel):
    job_url: Optional[str] = None
    job_text: Optional[str] = Field(None, description="Raw job description if no URL")
    max_out_tokens: int = Field(6000, ge=500, le=8192)
    include_insights: bool = True
    include_evaluation: bool = True


def execute_draft(body: DraftBody, workspace_id: str) -> Dict[str, Any]:
    url = (body.job_url or "").strip()
    paste = (body.job_text or "").strip()
    if not url and not paste:
        raise ValueError("Provide either job_url or job_text.")
    if url and paste:
        raise ValueError("Send only one of job_url or job_text.")
    try:
        spec = job_spec_mod.job_spec_from_url(url) if url else job_spec_mod.job_spec_from_paste(paste)
    except Exception as e:
        raise RuntimeError(f"Could not load job spec: {e}") from e
    ws = ws_mod.require_workspace(workspace_id)
    global_cfg = load_config().jobshunt
    cfg = ws_mod.effective_jobshunt_settings(ws, global_cfg)
    vault = ws_mod.effective_vault_path(ws, global_cfg)
    try:
        vault_txt, used, vsrc = vault_summary.vault_text_for_tailor(vault, cfg, workspace_id)
    except ImportError as e:
        raise ImportError(
            "Reading this résumé format needs optional packages: pip install 'jobshunt[export]'. "
            + str(e)
        ) from e
    story_ctx = ""
    if global_cfg.use_story_bank_in_draft:
        story_ctx = story_bank.format_for_tailor(workspace_id, max_chars=4000)
    resume_text = tailor.compose_resume_text(
        spec,
        vault_txt,
        title_case_name=global_cfg.display_name_title_case,
        max_out_tokens=body.max_out_tokens,
        story_bank_context=story_ctx,
    )
    refine_meta = None
    if global_cfg.auto_refine_after_draft:
        ref = resume_refine.refine_resume_for_ats(spec, resume_text, max_rounds=3)
        resume_text = ref["resume_text"]
        refine_meta = {
            "rounds": ref["rounds"],
            "stopped_reason": ref["stopped_reason"],
        }
    spec_cap = 32_000
    spec_for_client = spec[:spec_cap] if len(spec) > spec_cap else spec
    try:
        insight_payload = insights.build_insights(
            spec, resume_text, use_llm=body.include_insights
        )
    except Exception:
        insight_payload = {
            "heuristic_ats": insights.heuristic_ats(spec, resume_text),
            "llm": None,
        }
    eval_payload = None
    if body.include_evaluation:
        try:
            eval_payload = evaluation.build_evaluation(
                spec,
                resume_text,
                cfg=cfg,
                use_llm=True,
            )
        except Exception:
            eval_payload = None
    return {
        "resume_text": resume_text,
        "vault_files_used": used,
        "vault_context_source": vsrc,
        "job_spec_preview": spec[:2000],
        "job_spec_used": spec_for_client,
        "insights": insight_payload,
        "evaluation": eval_payload,
        "refine_meta": refine_meta,
    }


@router.post("/draft")
def draft(
    body: DraftBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    try:
        return execute_draft(body, workspace_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except ImportError as e:
        raise HTTPException(501, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            502,
            "Could not reach the LLM HTTP endpoint. In Job Hunt → AI settings, check **Base URL** "
            "(must be a real host, e.g. `https://api.openai.com/v1` or your proxy), DNS/VPN, and "
            f"that the service is up. Detail: {e}",
        ) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        en = type(e).__name__
        em = str(e).lower()
        if en == "APIConnectionError" or "nodename nor servname" in em or "name or service not known" in em:
            raise HTTPException(
                502,
                "Could not connect to the LLM provider (network/DNS). Check **AI settings** (Base URL, "
                "API key) and your network. If you use Anthropic, verify the SDK can reach "
                f"`api.anthropic.com` or your custom base URL. Detail: {e}",
            ) from e
        raise


@router.post("/compose")
def compose_alias(
    body: DraftBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    try:
        return execute_draft(body, workspace_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except ImportError as e:
        raise HTTPException(501, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(502, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:
        raise HTTPException(502, str(e)) from e


class InsightsBody(BaseModel):
    job_spec: str
    resume_text: str
    use_llm: bool = True


@router.post("/insights")
def compute_insights(body: InsightsBody) -> Dict[str, Any]:
    if not (body.resume_text or "").strip():
        raise HTTPException(400, "resume_text is required.")
    try:
        return insights.build_insights(
            (body.job_spec or "")[:50_000],
            body.resume_text,
            use_llm=body.use_llm,
        )
    except Exception as e:
        raise HTTPException(502, str(e)) from e


class RefineResumeBody(BaseModel):
    job_spec: str = ""
    resume_text: str = ""
    max_rounds: int = Field(3, ge=1, le=6)


@router.post("/refine-resume")
def refine_resume_route(body: RefineResumeBody) -> Dict[str, Any]:
    if not (body.resume_text or "").strip():
        raise HTTPException(400, "resume_text is required.")
    try:
        return resume_refine.refine_resume_for_ats(
            (body.job_spec or "")[:50_000],
            body.resume_text,
            max_rounds=body.max_rounds,
        )
    except Exception as e:
        raise HTTPException(502, str(e)) from e


class InsightItem(BaseModel):
    id: str = ""
    text: str = ""


class ApplyInsightItemsBody(BaseModel):
    job_spec: str = ""
    resume_text: str = ""
    items: List[InsightItem]
    mode: str = "same_section"
    section: Optional[str] = None


@router.post("/apply-insight-items")
def apply_insight_items_route(body: ApplyInsightItemsBody) -> Dict[str, Any]:
    if not (body.resume_text or "").strip():
        raise HTTPException(400, "resume_text is required.")
    items = [x.model_dump() for x in body.items]
    try:
        return insight_apply.apply_insight_items(
            (body.job_spec or "")[:50_000],
            body.resume_text,
            items,
            mode=body.mode,  # type: ignore[arg-type]
            section=body.section,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, str(e)) from e


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    resume_text: str = ""
    job_spec: str = ""
    last_insights: Optional[Dict[str, Any]] = None
    last_evaluation: Optional[Dict[str, Any]] = None


@router.post("/chat")
def chat_route(
    body: ChatBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    full = status(workspace_id)
    slim = {
        "workspace_id": full.get("workspace_id"),
        "workspace_name": full.get("workspace_name"),
        "vault_kind": full.get("vault_kind"),
        "vault_exists": full.get("vault_exists"),
        "summary_nonempty": full.get("summary_nonempty"),
        "vault_summary_pending_count": full.get("vault_summary_pending_count"),
        "use_vault_summary_for_context": full.get("use_vault_summary_for_context"),
        "use_story_bank_in_draft": full.get("use_story_bank_in_draft"),
        "scout_enabled": full.get("scout_enabled"),
        "auto_refine_after_draft": full.get("auto_refine_after_draft"),
    }
    msgs = [{"role": m.role, "content": m.content} for m in body.messages]
    try:
        return jobshunt_chat.run_chat_turn(
            messages=msgs,
            workspace_id=workspace_id,
            resume_text=body.resume_text,
            job_spec=body.job_spec,
            status_blob=slim,
            last_insights=body.last_insights,
            last_evaluation=body.last_evaluation,
        )
    except Exception as e:
        raise HTTPException(502, str(e)) from e


class EvaluationBody(BaseModel):
    job_spec: str
    resume_text: str


@router.post("/evaluation")
def compute_evaluation(
    body: EvaluationBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    if not (body.resume_text or "").strip():
        raise HTTPException(400, "resume_text is required.")
    ws = ws_mod.require_workspace(workspace_id)
    cfg = ws_mod.effective_jobshunt_settings(ws, load_config().jobshunt)
    try:
        ev = evaluation.build_evaluation(
            (body.job_spec or "")[:50_000],
            body.resume_text,
            cfg=cfg,
            use_llm=True,
        )
    except Exception as e:
        raise HTTPException(502, str(e)) from e
    if not ev:
        raise HTTPException(502, "Evaluation unavailable (LLM error or empty job spec).")
    return ev


@router.get("/applications")
def list_applications(workspace_id: str = Depends(workspace_id_dep)) -> List[Dict[str, Any]]:
    return pipeline.list_applications(workspace_id)


class ApplicationCreateBody(BaseModel):
    company: str = ""
    title: str = ""
    job_url: str = ""
    status: str = "new"
    notes: str = ""
    run_id: Optional[str] = None
    overall_score: Optional[float] = None


@router.post("/applications")
def create_application(
    body: ApplicationCreateBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    return pipeline.create_application(
        workspace_id,
        company=body.company,
        title=body.title,
        job_url=body.job_url,
        status=body.status,
        notes=body.notes,
        run_id=body.run_id,
        overall_score=body.overall_score,
    )


class ApplicationPatchBody(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    job_url: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    run_id: Optional[str] = None
    overall_score: Optional[float] = None


@router.put("/applications/{app_id}")
def update_application(
    app_id: str,
    body: ApplicationPatchBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    p = pipeline.update_application(workspace_id, app_id, body.model_dump(exclude_unset=True))
    if not p:
        raise HTTPException(404, "Application not found")
    return p


@router.delete("/applications/{app_id}")
def delete_application(
    app_id: str,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, bool]:
    ok = pipeline.delete_application(workspace_id, app_id)
    if not ok:
        raise HTTPException(404, "Application not found")
    return {"ok": True}


class StatusPatchBody(BaseModel):
    status: str


@router.patch("/applications/{app_id}/status")
def patch_application_status(
    app_id: str,
    body: StatusPatchBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    p = pipeline.patch_status(workspace_id, app_id, body.status)
    if not p:
        raise HTTPException(404, "Application not found or invalid status")
    return p


@router.get("/story-bank")
def get_story_bank(workspace_id: str = Depends(workspace_id_dep)) -> Dict[str, Any]:
    return {"pinned": story_bank.list_pinned(workspace_id)}


class PinStoryBody(BaseModel):
    title: str
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    reflection: str = ""
    source_evaluation_id: Optional[str] = None


@router.post("/story-bank/pin")
def pin_story(
    body: PinStoryBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    return story_bank.pin_story(
        workspace_id,
        title=body.title,
        situation=body.situation,
        task=body.task,
        action=body.action,
        result=body.result,
        reflection=body.reflection,
        source_evaluation_id=body.source_evaluation_id,
    )


@router.delete("/story-bank/{story_id}")
def unpin_story(
    story_id: str,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, bool]:
    if not story_bank.unpin_story(workspace_id, story_id):
        raise HTTPException(404, "Story not found")
    return {"ok": True}


@router.get("/negotiate/templates")
def negotiate_templates_list() -> Dict[str, Any]:
    return {"templates": negotiate.list_templates()}


class NegotiateBody(BaseModel):
    template_id: str
    context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/negotiate/personalize")
def negotiate_personalize(body: NegotiateBody) -> Dict[str, str]:
    try:
        return negotiate.personalize_template(body.template_id, context=body.context)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, str(e)) from e


class BatchItem(BaseModel):
    job_url: Optional[str] = None
    job_text: Optional[str] = None


class BatchDraftBody(BaseModel):
    items: List[BatchItem] = Field(default_factory=list)
    max_out_tokens: int = Field(6000, ge=500, le=8192)
    include_insights: bool = False
    include_evaluation: bool = False


def _batch_worker_item(
    workspace_id: str,
    item: Dict[str, Any],
    max_out: int,
    inc_ins: bool,
    inc_eval: bool,
) -> Dict[str, Any]:
    body = DraftBody(
        job_url=item.get("job_url"),
        job_text=item.get("job_text"),
        max_out_tokens=max_out,
        include_insights=inc_ins,
        include_evaluation=inc_eval,
    )
    try:
        out = execute_draft(body, workspace_id)
        return {"ok": True, "preview": (out.get("resume_text") or "")[:500], "evaluation": out.get("evaluation")}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except ImportError as e:
        return {"ok": False, "error": str(e)}
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/batch/draft")
def batch_draft(
    body: BatchDraftBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    items_in = body.items[:15]
    if not items_in:
        raise HTTPException(400, "items required (max 15)")
    serialized = [
        {
            "job_url": (it.job_url or "").strip() or None,
            "job_text": (it.job_text or "").strip() or None,
        }
        for it in items_in
    ]
    jid = batch_jobs.BatchJobStore.create(workspace_id, serialized)

    def worker(item: Dict[str, Any]) -> Dict[str, Any]:
        url = item.get("job_url")
        text = item.get("job_text")
        if url and text:
            return {"ok": False, "error": "item must have only job_url or job_text"}
        if not url and not text:
            return {"ok": False, "error": "empty item"}
        return _batch_worker_item(
            workspace_id,
            {"job_url": url, "job_text": text},
            body.max_out_tokens,
            body.include_insights,
            body.include_evaluation,
        )

    batch_jobs.run_batch_async(workspace_id, jid, worker)
    return {"batch_id": jid, "status": "queued"}


@router.get("/batch/{job_id}")
def batch_status(
    job_id: str,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    doc = batch_jobs.BatchJobStore.load(workspace_id, job_id)
    if not doc:
        raise HTTPException(404, "Unknown batch job")
    return doc


class ScoutBody(BaseModel):
    portals_yaml: str = Field(..., description="YAML with portals: list of url strings or {url: ...}")


@router.post("/scout")
def run_scout(body: ScoutBody) -> Dict[str, Any]:
    cfg = load_config().jobshunt
    try:
        hits = scout.run_scout(cfg, body.portals_yaml, max_pages=8)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except ImportError as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:
        raise HTTPException(502, str(e)) from e
    return {"hits": hits}


class ExportBody(BaseModel):
    resume_text: str
    basename: Optional[str] = None
    write_reserialized_pdf: bool = True


@router.post("/export")
def export_run(
    body: ExportBody,
    workspace_id: str = Depends(workspace_id_dep),
) -> Dict[str, Any]:
    errs = validate.validate_resume_text(body.resume_text)
    if errs:
        raise HTTPException(400, "; ".join(errs))
    rid = store.new_run_id()
    run_dir = store.jobshunt_runs_root(workspace_id) / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    stem = _slug(body.resume_text, body.basename)
    txt_path = run_dir / f"{stem}.txt"
    pdf_path = run_dir / f"{stem}.pdf"
    docx_path = run_dir / f"{stem}.docx"
    txt_path.write_text(body.resume_text.strip() + "\n", encoding="utf-8")
    try:
        render.build_pdf(body.resume_text, pdf_path)
        render.build_docx(body.resume_text, docx_path)
    except ImportError as e:
        raise HTTPException(
            501,
            "PDF/DOCX export needs optional deps: pip install 'jobshunt[export]'. " + str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    alt: Optional[str] = None
    if body.write_reserialized_pdf:
        ap = render.optional_reserialized_pdf(pdf_path)
        if ap:
            alt = str(ap.name)
    cfg = load_config().jobshunt
    wq = quote(workspace_id, safe="")
    store.write_run_record(
        run_dir,
        meta={
            "run_id": rid,
            "workspace_id": workspace_id,
            "stem": stem,
            "files": {
                "txt": txt_path.name,
                "pdf": pdf_path.name,
                "docx": docx_path.name,
                "reserialized_pdf": alt,
            },
            "output_dir": str(run_dir),
            "export_output_base": str(_output_base(cfg)),
        },
    )
    dl = {
        "txt": f"/api/agents/jobshunt/download/{rid}/{txt_path.name}?workspace_id={wq}",
        "pdf": f"/api/agents/jobshunt/download/{rid}/{pdf_path.name}?workspace_id={wq}",
        "docx": f"/api/agents/jobshunt/download/{rid}/{docx_path.name}?workspace_id={wq}",
    }
    if alt:
        dl["reserialized_pdf"] = f"/api/agents/jobshunt/download/{rid}/{alt}?workspace_id={wq}"
    return {
        "run_id": rid,
        "workspace_id": workspace_id,
        "stem": stem,
        "paths": {
            "txt": str(txt_path),
            "pdf": str(pdf_path),
            "docx": str(docx_path),
            "reserialized_pdf": str(run_dir / alt) if alt else None,
        },
        "download": dl,
    }


class ApplyHelperBody(BaseModel):
    run_id: Optional[str] = None


@router.post("/apply-helper")
def apply_helper(_body: ApplyHelperBody) -> Dict[str, Any]:
    cfg = load_config().jobshunt
    script = (cfg.apply_helper_script or "").strip()
    if not script:
        raise HTTPException(501, "Set jobshunt.apply_helper_script in config to enable.")
    if not cfg.allow_apply_subprocess:
        raise HTTPException(
            403,
            "Subprocess apply helper disabled. Set jobshunt.allow_apply_subprocess: true in config.",
        )
    p = Path(script).expanduser()
    if not p.is_file():
        raise HTTPException(400, f"Script not found: {p}")
    try:
        r = subprocess.run(
            [str(p)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise HTTPException(504, "apply-helper timed out") from e
    return {
        "returncode": r.returncode,
        "stdout": (r.stdout or "")[-8000:],
        "stderr": (r.stderr or "")[-8000:],
    }


@router.get("/runs")
def runs(
    limit: int = 30,
    workspace_id: str = Depends(workspace_id_dep),
) -> List[Dict[str, Any]]:
    return store.list_recent_runs(workspace_id, limit=min(limit, 100))


@router.get("/download/{run_id}/{filename}")
def download(
    run_id: str,
    filename: str,
    workspace_id: str = Depends(workspace_id_dep),
) -> FileResponse:
    if not re.match(r"^[\w.-]+\.(txt|pdf|docx)$", filename):
        raise HTTPException(400, "Invalid filename")
    d = store.safe_run_dir(workspace_id, run_id)
    if not d:
        raise HTTPException(404, "Unknown run")
    fp = (d / filename).resolve()
    if not str(fp).startswith(str(d.resolve())) or not fp.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(str(fp), filename=filename, media_type="application/octet-stream")
