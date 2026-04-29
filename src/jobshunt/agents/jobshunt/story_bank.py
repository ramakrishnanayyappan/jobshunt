"""STAR story bank — pinned stories for reuse in drafts and interviews (per workspace)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .workspaces import workspace_data_dir


def story_bank_path(workspace_id: str) -> Path:
    p = workspace_data_dir(workspace_id) / "story_bank.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(workspace_id: str) -> Dict[str, Any]:
    p = story_bank_path(workspace_id)
    if not p.is_file():
        return {"pinned": [], "schema_version": 1}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"pinned": [], "schema_version": 1}
    if not isinstance(d, dict):
        return {"pinned": [], "schema_version": 1}
    if not isinstance(d.get("pinned"), list):
        d["pinned"] = []
    return d


def _save(workspace_id: str, d: Dict[str, Any]) -> None:
    with open(story_bank_path(workspace_id), "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def list_pinned(workspace_id: str) -> List[Dict[str, Any]]:
    return list(_load(workspace_id).get("pinned") or [])


def pin_story(
    workspace_id: str,
    *,
    title: str,
    situation: str = "",
    task: str = "",
    action: str = "",
    result: str = "",
    reflection: str = "",
    source_evaluation_id: Optional[str] = None,
) -> Dict[str, Any]:
    d = _load(workspace_id)
    pinned: List[Dict[str, Any]] = list(d.get("pinned") or [])
    row = {
        "id": uuid.uuid4().hex[:24],
        "title": (title or "Untitled story")[:200],
        "situation": (situation or "")[:2000],
        "task": (task or "")[:2000],
        "action": (action or "")[:2000],
        "result": (result or "")[:2000],
        "reflection": (reflection or "")[:2000],
        "source_evaluation_id": (source_evaluation_id or "").strip() or None,
        "pinned_at": _now(),
    }
    pinned.insert(0, row)
    d["pinned"] = pinned[:50]
    _save(workspace_id, d)
    return row


def unpin_story(workspace_id: str, story_id: str) -> bool:
    d = _load(workspace_id)
    sid = (story_id or "").strip()
    pinned: List[Dict[str, Any]] = list(d.get("pinned") or [])
    new_p = [x for x in pinned if isinstance(x, dict) and x.get("id") != sid]
    if len(new_p) == len(pinned):
        return False
    d["pinned"] = new_p
    _save(workspace_id, d)
    return True


def format_for_tailor(workspace_id: str, max_chars: int = 4000) -> str:
    """Compact block to inject into résumé tailoring user message."""
    rows = list_pinned(workspace_id)[:12]
    if not rows:
        return ""
    lines: List[str] = [
        "Candidate story bank (use only as behavioral proof — do not invent employers or metrics):",
    ]
    for r in rows:
        title = str(r.get("title") or "Story")
        parts = []
        for label, key in (
            ("S", "situation"),
            ("T", "task"),
            ("A", "action"),
            ("R", "result"),
            ("Reflection", "reflection"),
        ):
            v = (r.get(key) or "").strip()
            if v:
                parts.append(f"{label}: {v}")
        if parts:
            lines.append(f"- {title}: " + " | ".join(parts))
        else:
            lines.append(f"- {title}")
    blob = "\n".join(lines)
    if len(blob) > max_chars:
        return blob[: max_chars - 20] + "\n…(truncated)"
    return blob
