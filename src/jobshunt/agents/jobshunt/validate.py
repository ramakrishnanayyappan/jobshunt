from __future__ import annotations

from typing import List

_VALID_HEADERS = {
    "SUMMARY",
    "CORE COMPETENCIES",
    "EXPERIENCE",
    "EDUCATION",
    "CERTIFICATIONS & TRAINING",
}


def validate_resume_text(text: str) -> List[str]:
    errs: List[str] = []
    lines = (text or "").replace("\r\n", "\n").split("\n")
    if len(lines) < 4:
        errs.append("Need at least 4 lines: full name, contact line, blank line, then a section header.")
        return errs
    if not lines[0].strip():
        errs.append("First line (your name) must not be empty.")
    if not lines[1].strip():
        errs.append("Second line (contact) must not be empty.")
    found = any(ln.strip() in _VALID_HEADERS for ln in lines)
    if not found:
        errs.append(
            "No recognized section header. Use one of: "
            + ", ".join(sorted(_VALID_HEADERS))
        )
    return errs
