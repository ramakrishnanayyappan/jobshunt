"""Apply structured insight items (quick tips, etc.) into a résumé draft via LLM."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Literal, Optional

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings

from .text_sanitize import sanitize_paste_artifacts

ALLOWED_SECTIONS = [
    "SUMMARY",
    "CORE COMPETENCIES",
    "EXPERIENCE",
    "EDUCATION",
    "CERTIFICATIONS & TRAINING",
]

Mode = Literal["same_section", "per_item"]

_APPLY_SYSTEM = """You revise a plain-text résumé by incorporating the user's selected suggestions.

Output rules:
- Reply with ONE JSON object only, no markdown. Keys: "resume_text" (string, full résumé body).
- The résumé must stay plain text: same global layout as typical ATS drafts (name line, contact, blank line,
  then ALL-CAPS section headers one per line: SUMMARY, CORE COMPETENCIES, EXPERIENCE, EDUCATION,
  CERTIFICATIONS & TRAINING as applicable).
- Do not invent employers, titles, dates, degrees, or metrics. Only merge truthful wording.
- Integrate each suggestion naturally in the target section(s). If mode is per_item, use the section given for that item.
"""


def _strip_code_fence(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        lines = lines[1:] if lines else lines
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        t = "\n".join(lines).strip()
    return t


def _parse_apply_response(raw: str) -> Optional[str]:
    t = _strip_code_fence(raw)
    for attempt in (t, re.sub(r"^```\w*\n|```$", "", t, flags=re.MULTILINE).strip()):
        if not attempt:
            continue
        try:
            d = json.loads(attempt)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}\s*$", attempt)
            if not m:
                continue
            try:
                d = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
        rt = d.get("resume_text")
        if isinstance(rt, str) and rt.strip():
            return rt.strip()
    return None


def _llm_apply(
    job_spec: str,
    resume_text: str,
    payload_desc: str,
    *,
    max_out_tokens: int = 6000,
) -> str:
    user = (
        f"JOB POSTING (context):\n{(job_spec or '')[:12000]}\n\n"
        f"CURRENT RÉSUMÉ:\n{(resume_text or '')[:12000]}\n\n"
        f"TASK:\n{payload_desc}\n"
    )

    def _once(a: AISettings) -> str:
        if a.provider == "anthropic" and a.api_key:
            from anthropic import Anthropic

            cl = Anthropic(
                api_key=a.api_key,
                base_url=a.base_url or "https://api.anthropic.com",
            )
            m = a.model or "claude-3-5-haiku-20241022"
            cap = min(max_out_tokens, a.max_tokens, 8192)
            r = cl.messages.create(
                model=m,
                max_tokens=cap,
                temperature=0.25,
                system=_APPLY_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            b0 = r.content[0]
            return b0.text if b0.type == "text" else str(b0)
        return chat_text_impl(
            a,
            [{"role": "user", "content": user}],
            _APPLY_SYSTEM,
            max_out_tokens,
        )

    return run_with_llm_fallback("jobshunt", _once)


def apply_insight_items(
    job_spec: str,
    resume_text: str,
    items: List[Dict[str, str]],
    *,
    mode: Mode,
    section: Optional[str] = None,
    max_out_tokens: int = 6000,
) -> Dict[str, Any]:
    job_spec = sanitize_paste_artifacts(job_spec or "")
    resume_text = sanitize_paste_artifacts(resume_text or "")
    cleaned: List[Dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        tid = str(it.get("id") or "").strip() or f"item{len(cleaned)}"
        txt = sanitize_paste_artifacts(str(it.get("text") or "").strip())
        if txt:
            cleaned.append({"id": tid, "text": txt})
    if not cleaned:
        raise ValueError("No items to apply.")
    if mode == "same_section":
        sec = (section or "").strip()
        if sec not in ALLOWED_SECTIONS:
            raise ValueError(
                f"section must be one of: {', '.join(ALLOWED_SECTIONS)} for same_section mode."
            )
        bullets = "\n".join(f"- [{x['id']}] {x['text']}" for x in cleaned)
        desc = (
            f"Mode: same_section. Place ALL of the following into the {sec} section:\n{bullets}\n"
            f"Return JSON with key resume_text only."
        )
    else:
        lines = []
        for i, x in enumerate(cleaned):
            lines.append(
                f"{i + 1}. id={x['id']!r} text={x['text']!r} "
                f"→ choose the single best section from {ALLOWED_SECTIONS!r} for this item only."
            )
        desc = (
            "Mode: per_item. For each numbered suggestion, pick the best section and merge it there.\n"
            + "\n".join(lines)
            + "\nReturn JSON with key resume_text only."
        )
    raw = _llm_apply(job_spec, resume_text, desc, max_out_tokens=max_out_tokens)
    parsed = _parse_apply_response(raw)
    if not parsed:
        raise RuntimeError("Model did not return valid JSON with resume_text.")
    return {
        "resume_text": sanitize_paste_artifacts(parsed),
        "applied": [{"id": x["id"], "text": x["text"]} for x in cleaned],
        "mode": mode,
        "section": section if mode == "same_section" else None,
    }
