"""Master résumé vault summary + manifest of incorporated files (reduces LLM context size)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings, JobShuntSettings

from . import resume_vault
from .workspaces import workspace_data_dir

MANIFEST_VERSION = 1
SUMMARY_MAX_CHARS = 48_000
REBUILD_BUNDLE_MAX_CHARS = 120_000
MERGE_MAX_OUT_TOKENS = 6000

_MERGE_SYSTEM = """You maintain a single plain-text "master career summary" for a candidate.

The user will give you the CURRENT summary (may be empty) plus text extracted from ONE résumé file.

Task: Merge the new material into the summary. Rules:
- Plain text only, no markdown fences.
- Preserve facts (employers, titles, dates, metrics) from BOTH; deduplicate obvious repeats.
- Prefer concise bullets and short paragraphs; prioritize recent and strongest impact.
- If the new file overlaps heavily, consolidate — do not duplicate long blocks.
- Total output must stay under 40000 characters; summarize if needed.
- Do not invent employers, degrees, or credentials not present in the inputs."""

_REBUILD_SYSTEM = """You produce ONE plain-text master career summary from raw résumé material that may include multiple files.

Rules:
- Plain text only, no markdown fences.
- Preserve key facts: roles, companies, dates, skills, education, metrics.
- Deduplicate across files; prioritize clarity and ATS-friendly phrasing.
- Stay under 40000 characters.
- Do not invent content not present in the source."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jobshunt_data_dir(workspace_id: str = "default") -> Path:
    """Per-workspace data directory (manifest, changelog, default summary file)."""
    return workspace_data_dir(workspace_id)


def manifest_path(workspace_id: str) -> Path:
    return jobshunt_data_dir(workspace_id) / "vault_summary_manifest.json"


def changelog_path(workspace_id: str) -> Path:
    return jobshunt_data_dir(workspace_id) / "vault_summary_changelog.jsonl"


def summary_file_path(cfg: JobShuntSettings, workspace_id: str) -> Path:
    raw = (cfg.vault_summary_path or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (jobshunt_data_dir(workspace_id) / "vault_summary.txt").resolve()


def _load_manifest(workspace_id: str) -> Dict[str, Any]:
    p = manifest_path(workspace_id)
    if not p.is_file():
        return {"schema_version": MANIFEST_VERSION, "updated_at": "", "files": []}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"schema_version": MANIFEST_VERSION, "updated_at": "", "files": []}
    if not isinstance(d, dict):
        return {"schema_version": MANIFEST_VERSION, "updated_at": "", "files": []}
    if d.get("schema_version") != MANIFEST_VERSION:
        d = {"schema_version": MANIFEST_VERSION, "updated_at": d.get("updated_at", ""), "files": []}
    files = d.get("files")
    if not isinstance(files, list):
        d["files"] = []
    return d


def _save_manifest(workspace_id: str, d: Dict[str, Any]) -> None:
    d = dict(d)
    d["schema_version"] = MANIFEST_VERSION
    d["updated_at"] = _now_iso()
    files = d.get("files")
    if not isinstance(files, list):
        d["files"] = []
    p = manifest_path(workspace_id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def _changelog_append(workspace_id: str, record: Dict[str, Any]) -> None:
    line = json.dumps({**record, "ts": _now_iso()}, ensure_ascii=False) + "\n"
    p = changelog_path(workspace_id)
    with open(p, "a", encoding="utf-8") as f:
        f.write(line)


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def _fingerprint(path: Path) -> Tuple[int, str]:
    st = path.stat()
    text = resume_vault.read_resume_text(path)
    return int(st.st_mtime_ns), _sha256_text(text)


def manifest_index(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for ent in manifest.get("files") or []:
        if isinstance(ent, dict):
            key = str(ent.get("path") or "").strip()
            if key:
                out[key] = ent
    return out


def list_pending_vault_files(
    vault: Path, cfg: JobShuntSettings, workspace_id: str
) -> List[Dict[str, Any]]:
    """Paths in vault that are missing from manifest or changed since incorporation."""
    manifest = _load_manifest(workspace_id)
    idx = manifest_index(manifest)
    pending: List[Dict[str, Any]] = []
    for src in resume_vault.list_vault_sources(vault):
        try:
            resolved = str(src.resolve())
        except OSError:
            continue
        try:
            mtime_ns, chash = _fingerprint(src)
        except (OSError, ImportError):
            continue
        row = idx.get(resolved)
        if not row:
            pending.append(
                {
                    "path": resolved,
                    "display_name": src.name,
                    "reason": "new",
                }
            )
            continue
        try:
            old_mtime = int(row.get("mtime_ns") or 0)
        except (TypeError, ValueError):
            old_mtime = 0
        old_hash = str(row.get("content_sha256") or "")
        if mtime_ns != old_mtime or chash != old_hash:
            pending.append(
                {
                    "path": resolved,
                    "display_name": src.name,
                    "reason": "modified",
                }
            )
    return pending


def incorporated_paths(cfg: JobShuntSettings, workspace_id: str) -> List[str]:
    """Resolved paths recorded in manifest (for API compatibility with vault_files_used)."""
    m = _load_manifest(workspace_id)
    out: List[str] = []
    for ent in m.get("files") or []:
        if isinstance(ent, dict):
            p = str(ent.get("path") or "").strip()
            if p:
                out.append(p)
    return out


def read_summary_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _write_summary(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (text or "").strip()
    path.write_text(body + ("\n" if body else ""), encoding="utf-8")


def _strip_code_fence(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        lines = lines[1:] if lines else lines
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        t = "\n".join(lines).strip()
    return t


def _llm_merge(existing: str, file_name: str, new_resume_text: str) -> str:
    user = (
        f"--- CURRENT MASTER SUMMARY ---\n{(existing or '')[:SUMMARY_MAX_CHARS]}\n\n"
        f"--- NEW FILE: {file_name} ---\n{(new_resume_text or '')[:80_000]}\n"
    )

    def _once(a: AISettings) -> str:
        if a.provider == "anthropic" and a.api_key:
            from anthropic import Anthropic

            cl = Anthropic(
                api_key=a.api_key,
                base_url=a.base_url or "https://api.anthropic.com",
            )
            m = a.model or "claude-3-5-haiku-20241022"
            cap = min(MERGE_MAX_OUT_TOKENS, a.max_tokens, 8192)
            r = cl.messages.create(
                model=m,
                max_tokens=cap,
                temperature=0.2,
                system=_MERGE_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            b0 = r.content[0]
            return b0.text if b0.type == "text" else str(b0)
        return chat_text_impl(
            a,
            [{"role": "user", "content": user}],
            _MERGE_SYSTEM,
            MERGE_MAX_OUT_TOKENS,
        )

    raw = run_with_llm_fallback("jobshunt", _once)
    out = _strip_code_fence(raw).strip()
    return out[:SUMMARY_MAX_CHARS]


def _llm_rebuild(bundle_text: str) -> str:
    user = "--- SOURCE MATERIAL (multiple files may be concatenated) ---\n" + (bundle_text or "")[
        :REBUILD_BUNDLE_MAX_CHARS
    ]

    def _once(a: AISettings) -> str:
        if a.provider == "anthropic" and a.api_key:
            from anthropic import Anthropic

            cl = Anthropic(
                api_key=a.api_key,
                base_url=a.base_url or "https://api.anthropic.com",
            )
            m = a.model or "claude-3-5-haiku-20241022"
            cap = min(MERGE_MAX_OUT_TOKENS, a.max_tokens, 8192)
            r = cl.messages.create(
                model=m,
                max_tokens=cap,
                temperature=0.2,
                system=_REBUILD_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            b0 = r.content[0]
            return b0.text if b0.type == "text" else str(b0)
        return chat_text_impl(
            a,
            [{"role": "user", "content": user}],
            _REBUILD_SYSTEM,
            MERGE_MAX_OUT_TOKENS,
        )

    raw = run_with_llm_fallback("jobshunt", _once)
    out = _strip_code_fence(raw).strip()
    return out[:SUMMARY_MAX_CHARS]


def _upsert_manifest_entry(
    workspace_id: str, manifest: Dict[str, Any], path: Path, display_name: str
) -> None:
    mtime_ns, chash = _fingerprint(path)
    resolved = str(path.resolve())
    files = [f for f in (manifest.get("files") or []) if isinstance(f, dict) and str(f.get("path")) != resolved]
    files.append(
        {
            "path": resolved,
            "display_name": display_name,
            "mtime_ns": mtime_ns,
            "content_sha256": chash,
            "incorporated_at": _now_iso(),
        }
    )
    manifest["files"] = files
    _save_manifest(workspace_id, manifest)


def merge_pending(
    vault: Path,
    cfg: JobShuntSettings,
    workspace_id: str,
    *,
    only_pending: bool = True,
    paths_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Merge new/changed files into summary using LLM per file."""
    sp = summary_file_path(cfg, workspace_id)
    pending = list_pending_vault_files(vault, cfg, workspace_id)
    if paths_filter:
        allow = {str(Path(p).expanduser().resolve()) for p in paths_filter}
        pending = [p for p in pending if p["path"] in allow]
    if not pending and only_pending:
        return {"ok": True, "merged": 0, "message": "No pending files."}
    manifest = _load_manifest(workspace_id)
    if not only_pending:
        manifest["files"] = []
        _save_manifest(workspace_id, manifest)
        manifest = _load_manifest(workspace_id)
        current = ""
        to_process = [
            {
                "path": str(s.resolve()),
                "display_name": s.name,
                "reason": "full_merge",
            }
            for s in resume_vault.list_vault_sources(vault)
        ]
        if paths_filter:
            allow = {str(Path(p).expanduser().resolve()) for p in paths_filter}
            to_process = [p for p in to_process if p["path"] in allow]
    else:
        current = read_summary_text(sp)
        to_process = pending
    merged = 0
    seen: set[str] = set()
    for item in to_process:
        rp = item["path"]
        if rp in seen:
            continue
        seen.add(rp)
        p = Path(rp)
        if not p.is_file():
            continue
        try:
            body = resume_vault.read_resume_text(p)
        except ImportError:
            raise
        except OSError:
            continue
        if not body.strip():
            continue
        name = item.get("display_name") or p.name
        current = _llm_merge(current, name, body)
        _write_summary(sp, current)
        _upsert_manifest_entry(workspace_id, manifest, p, name)
        merged += 1
        _changelog_append(workspace_id, {"action": "incorporate", "path": rp, "display_name": name})
    return {"ok": True, "merged": merged, "summary_path": str(sp)}


def rebuild_from_vault(
    vault: Path,
    cfg: JobShuntSettings,
    workspace_id: str,
) -> Dict[str, Any]:
    """Replace summary from full vault bundle (single LLM condensation)."""
    try:
        bundle, used_paths = resume_vault.read_vault_bundle(
            vault,
            max_chars=cfg.max_vault_chars,
            max_files=cfg.max_vault_files,
        )
    except ImportError:
        raise
    if not bundle.strip():
        raise ValueError("No readable résumé text in the vault.")
    text = _llm_rebuild(bundle)
    sp = summary_file_path(cfg, workspace_id)
    _write_summary(sp, text)
    manifest = _load_manifest(workspace_id)
    manifest["files"] = []
    _save_manifest(workspace_id, manifest)
    for rel in used_paths:
        p = Path(rel)
        if p.is_file():
            _upsert_manifest_entry(workspace_id, manifest, p, p.name)
    _changelog_append(workspace_id, {"action": "rebuild", "paths": used_paths})
    return {"ok": True, "summary_path": str(sp), "source_files": len(used_paths)}


def status_payload(vault: Path, cfg: JobShuntSettings, workspace_id: str) -> Dict[str, Any]:
    sp = summary_file_path(cfg, workspace_id)
    pending = list_pending_vault_files(vault, cfg, workspace_id)
    manifest = _load_manifest(workspace_id)
    txt = read_summary_text(sp)
    return {
        "use_vault_summary_for_context": cfg.use_vault_summary_for_context,
        "vault_summary_path": str(sp),
        "vault_summary_path_display": _path_display(str(sp)),
        "summary_char_count": len(txt),
        "summary_nonempty": bool(txt.strip()),
        "manifest_file_count": len(manifest.get("files") or []),
        "manifest_updated_at": manifest.get("updated_at") or "",
        "vault_summary_pending": pending,
        "vault_summary_pending_count": len(pending),
        "block_draft_when_vault_summary_stale": cfg.block_draft_when_vault_summary_stale,
        "vault_summary_config_path": (cfg.vault_summary_path or "").strip(),
    }


def _path_display(path: str) -> str:
    """Tilde-home shorten for UI."""
    path = path.rstrip("/")
    home = str(Path.home())
    if path.startswith(home + "/") or path == home:
        return "~" + path[len(home) :] if path != home else "~"
    return path


def vault_text_for_tailor(
    vault: Path,
    cfg: JobShuntSettings,
    workspace_id: str,
) -> Tuple[str, List[str], str]:
    """
    Returns (vault_plaintext_for_tailor, paths_used_for_metadata, source_label).
    source_label is "summary" or "bundle".
    """
    if cfg.use_vault_summary_for_context:
        sp = summary_file_path(cfg, workspace_id)
        txt = read_summary_text(sp)
        if not txt.strip():
            raise ValueError(
                "Vault summary is empty. Use Vault summary → Rebuild from vault or Update pending, "
                "or turn off “Use vault summary for context” in settings."
            )
        if cfg.block_draft_when_vault_summary_stale:
            pend = list_pending_vault_files(vault, cfg, workspace_id)
            if pend:
                names = ", ".join(p["display_name"] for p in pend[:10])
                more = f" (+{len(pend) - 10} more)" if len(pend) > 10 else ""
                raise ValueError(
                    "Vault summary is stale: new or changed résumé(s) not merged: "
                    f"{names}{more}. Update the vault summary in Job hunt, or disable blocking in settings."
                )
        used = incorporated_paths(cfg, workspace_id)
        return txt.strip(), used, "summary"
    vault_txt, used = resume_vault.read_vault_bundle(
        vault,
        max_chars=cfg.max_vault_chars,
        max_files=cfg.max_vault_files,
    )
    return vault_txt, used, "bundle"
