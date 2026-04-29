from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

_VAULT_EXTS = {".txt", ".md", ".docx", ".pdf"}


def is_supported_resume_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in _VAULT_EXTS


def list_vault_sources(vault: Path) -> List[Path]:
    p = vault.expanduser()
    if not p.exists():
        return []
    if p.is_file():
        return [p] if is_supported_resume_file(p) else []
    if p.is_dir():
        out: List[Path] = []
        for child in p.iterdir():
            if is_supported_resume_file(child):
                out.append(child)
        out.sort(key=lambda x: x.stat().st_mtime_ns, reverse=True)
        return out
    return []


def read_resume_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if ext == ".docx":
        try:
            from docx import Document
        except ImportError as e:
            raise ImportError(
                "Reading .docx needs python-docx: pip install jobshunt[export]"
            ) from e
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError(
                "Reading .pdf needs pypdf: pip install jobshunt[export]"
            ) from e
        r = PdfReader(str(path))
        parts: List[str] = []
        for page in r.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
        return "\n\n".join(parts)
    return ""


def read_vault_bundle(
    vault: Path,
    *,
    max_chars: int,
    max_files: int,
) -> Tuple[str, List[str]]:
    files = list_vault_sources(vault)[: max(0, max_files)]
    parts: List[str] = []
    used: List[str] = []
    total = 0
    for f in files:
        try:
            chunk = read_resume_text(f)
        except OSError:
            continue
        except ImportError:
            raise
        if not chunk.strip():
            continue
        header = f"\n\n===== FILE: {f.name} =====\n"
        add_len = len(header) + len(chunk)
        if total + add_len > max_chars and parts:
            break
        parts.append(header + chunk)
        used.append(str(f.resolve()))
        total += add_len
        if total >= max_chars:
            break
    return "".join(parts).strip(), used
