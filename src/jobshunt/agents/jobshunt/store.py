from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .workspaces import workspace_data_dir


def jobshunt_runs_root(workspace_id: str) -> Path:
    p = workspace_data_dir(workspace_id) / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]


def write_run_record(
    run_dir: Path,
    *,
    meta: Dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / "run.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def list_recent_runs(workspace_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    root = jobshunt_runs_root(workspace_id)
    if not root.is_dir():
        return []
    dirs = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda x: x.name, reverse=True)
    out: List[Dict[str, Any]] = []
    for d in dirs[:limit]:
        jp = d / "run.json"
        if jp.is_file():
            try:
                with open(jp, encoding="utf-8") as f:
                    out.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                out.append({"run_id": d.name, "path": str(d)})
        else:
            out.append({"run_id": d.name, "path": str(d)})
    return out


def safe_run_dir(workspace_id: str, run_id: str) -> Optional[Path]:
    import re
    if not re.match(r"^[0-9]{8}T[0-9]{6}_[0-9a-f]{8}$", (run_id or "").strip()):
        return None
    base = jobshunt_runs_root(workspace_id).resolve()
    cand = (base / run_id.strip()).resolve()
    if not str(cand).startswith(str(base)) or not cand.is_dir():
        return None
    return cand
