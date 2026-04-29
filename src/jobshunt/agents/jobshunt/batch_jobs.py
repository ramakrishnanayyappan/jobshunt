"""Batch draft jobs — sequential processing with persisted status (per workspace)."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .workspaces import workspace_data_dir


def batch_root(workspace_id: str) -> Path:
    p = workspace_data_dir(workspace_id) / "batch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def job_file(workspace_id: str, job_id: str) -> Path:
    return batch_root(workspace_id) / f"{job_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BatchJobStore:
    _lock = threading.Lock()

    @classmethod
    def create(cls, workspace_id: str, items: List[Dict[str, Any]]) -> str:
        jid = uuid.uuid4().hex[:16]
        doc = {
            "id": jid,
            "status": "queued",
            "created_at": _now(),
            "updated_at": _now(),
            "items": items,
            "results": [],
            "error": None,
        }
        with cls._lock:
            with open(job_file(workspace_id, jid), "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
        return jid

    @classmethod
    def load(cls, workspace_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        p = job_file(workspace_id, job_id)
        if not p.is_file():
            return None
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    @classmethod
    def save(cls, workspace_id: str, doc: Dict[str, Any]) -> None:
        jid = doc.get("id")
        if not jid:
            return
        doc["updated_at"] = _now()
        with cls._lock:
            with open(job_file(workspace_id, str(jid)), "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)


def run_batch_async(
    workspace_id: str,
    job_id: str,
    worker: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> None:
    def _run() -> None:
        doc = BatchJobStore.load(workspace_id, job_id)
        if not doc:
            return
        doc["status"] = "running"
        doc["results"] = []
        doc["error"] = None
        BatchJobStore.save(workspace_id, doc)
        items = doc.get("items") or []
        try:
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                try:
                    res = worker(item)
                except Exception as e:
                    res = {"index": i, "ok": False, "error": str(e)}
                doc.setdefault("results", []).append(res)
                BatchJobStore.save(workspace_id, doc)
            doc["status"] = "done"
        except Exception as e:
            doc["status"] = "failed"
            doc["error"] = str(e)
        BatchJobStore.save(workspace_id, doc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
