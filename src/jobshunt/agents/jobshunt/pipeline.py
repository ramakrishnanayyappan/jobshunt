"""Application pipeline (CRUD) — local JSON store per workspace."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .workspaces import workspace_data_dir

ALLOWED_STATUS = frozenset(
    {"new", "evaluated", "drafted", "exported", "applied", "rejected", "archived"}
)


def pipeline_path(workspace_id: str) -> Path:
    p = workspace_data_dir(workspace_id) / "pipeline.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(workspace_id: str) -> Dict[str, Any]:
    p = pipeline_path(workspace_id)
    if not p.is_file():
        return {"applications": [], "schema_version": 1}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"applications": [], "schema_version": 1}
    if not isinstance(d, dict):
        return {"applications": [], "schema_version": 1}
    apps = d.get("applications")
    if not isinstance(apps, list):
        d["applications"] = []
    return d


def _save(workspace_id: str, d: Dict[str, Any]) -> None:
    p = pipeline_path(workspace_id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def list_applications(workspace_id: str) -> List[Dict[str, Any]]:
    return list(_load(workspace_id).get("applications") or [])


def get_application(workspace_id: str, app_id: str) -> Optional[Dict[str, Any]]:
    aid = (app_id or "").strip()
    for a in list_applications(workspace_id):
        if isinstance(a, dict) and a.get("id") == aid:
            return a
    return None


def create_application(
    workspace_id: str,
    *,
    company: str,
    title: str,
    job_url: str = "",
    status: str = "new",
    notes: str = "",
    run_id: Optional[str] = None,
    overall_score: Optional[float] = None,
) -> Dict[str, Any]:
    d = _load(workspace_id)
    apps: List[Dict[str, Any]] = list(d.get("applications") or [])
    now = _now_iso()
    row = {
        "id": uuid.uuid4().hex,
        "company": (company or "")[:200],
        "title": (title or "")[:300],
        "job_url": (job_url or "")[:2000],
        "status": status if status in ALLOWED_STATUS else "new",
        "notes": (notes or "")[:8000],
        "run_id": (run_id or "").strip() or None,
        "overall_score": overall_score,
        "created_at": now,
        "updated_at": now,
    }
    apps.insert(0, row)
    d["applications"] = apps
    _save(workspace_id, d)
    return row


def update_application(
    workspace_id: str, app_id: str, patch: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    d = _load(workspace_id)
    apps: List[Dict[str, Any]] = list(d.get("applications") or [])
    out: Optional[Dict[str, Any]] = None
    for i, a in enumerate(apps):
        if not isinstance(a, dict) or a.get("id") != app_id:
            continue
        new = dict(a)
        if "company" in patch:
            new["company"] = str(patch["company"] or "")[:200]
        if "title" in patch:
            new["title"] = str(patch["title"] or "")[:300]
        if "job_url" in patch:
            new["job_url"] = str(patch["job_url"] or "")[:2000]
        if "status" in patch:
            st = str(patch["status"] or "new")
            new["status"] = st if st in ALLOWED_STATUS else a.get("status", "new")
        if "notes" in patch:
            new["notes"] = str(patch["notes"] or "")[:8000]
        if "run_id" in patch:
            r = patch["run_id"]
            new["run_id"] = (str(r).strip() if r else None) or None
        if "overall_score" in patch:
            os_ = patch["overall_score"]
            new["overall_score"] = float(os_) if os_ is not None and str(os_) != "" else None
        new["updated_at"] = _now_iso()
        apps[i] = new
        out = new
        break
    if out is None:
        return None
    d["applications"] = apps
    _save(workspace_id, d)
    return out


def delete_application(workspace_id: str, app_id: str) -> bool:
    d = _load(workspace_id)
    apps = [a for a in (d.get("applications") or []) if isinstance(a, dict) and a.get("id") != app_id]
    if len(apps) == len(d.get("applications") or []):
        return False
    d["applications"] = apps
    _save(workspace_id, d)
    return True


def patch_status(workspace_id: str, app_id: str, status: str) -> Optional[Dict[str, Any]]:
    st = str(status or "").strip()
    if st not in ALLOWED_STATUS:
        return None
    return update_application(workspace_id, app_id, {"status": st})
