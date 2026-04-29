"""Structured offer evaluation, provider-agnostic via configured LLM."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings, JobShuntSettings

SCHEMA_VERSION = 1

_EVAL_SYSTEM = """You help a candidate decide whether a job is worth pursuing. Reply with ONE JSON object only, no markdown.

Required keys (exactly):
- "overall_score": number from 1.0 to 5.0 (one decimal ok) — holistic fit vs the candidate's materials (not keyword-only).
- "dimensions": array of objects, each with "id" (short snake_case), "label" (human string), "score" (1-5 int), "rationale" (one sentence).
  Cover at least these themes across the array: role_fit, level_seniority, impact_scope, comp_awareness, culture_process, growth_risk.
- "role_summary": string — 2-4 sentences: what the role is and who they want.
- "cv_match": string — how the vault/résumé material aligns; be grounded in provided text only.
- "gaps": array of 3-8 strings — concrete gaps or risks (skills, level, domain).
- "level_strategy": string — e.g. stretch role vs comfortable; how to position in interviews.
- "comp_notes": string — brief compensation / market realism notes; MUST say estimates may be wrong and user should verify.
- "personalization_hooks": array of 4-8 strings — truthful hooks to weave into cover letter or intro emails.
- "interview_prep": array of 4-8 strings — STAR-style bullets (Situation/Task/Action/Result compressed into one line each).
- "story_candidates": array of 0-5 objects for a story bank; each with optional "title" and strings "situation","task","action","result","reflection" (can be empty strings if unknown).
- "recommendation": one of exactly "apply", "maybe", "skip"
- "recommendation_rationale": string — 2-5 sentences; be candid. If weak fit, say skip.

Rules: Valid JSON only. No invented employers or credentials for the candidate. If vault is thin, say so in cv_match."""


def _llm_eval(system: str, user: str, *, max_out_tokens: int) -> str:
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
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            b0 = r.content[0]
            return b0.text if b0.type == "text" else str(b0)
        return chat_text_impl(
            a,
            [{"role": "user", "content": user}],
            system,
            max_out_tokens,
        )

    return run_with_llm_fallback("jobshunt", _once)


def _strip_code_fence(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        t = "\n".join(lines).strip()
    return t


def _extract_json_object(s: str) -> str:
    """If the model wraps JSON in prose, take the outermost {...} span."""
    i = s.find("{")
    j = s.rfind("}")
    if i >= 0 and j > i:
        return s[i : j + 1]
    return s


def _parse_evaluation_json(raw: str) -> Optional[Dict[str, Any]]:
    t = _strip_code_fence(raw)
    candidates = [
        t,
        re.sub(r"^```\w*\n|```$", "", t, flags=re.MULTILINE).strip(),
        _extract_json_object(t),
    ]
    seen: set[str] = set()
    for attempt in candidates:
        if not attempt or attempt in seen:
            continue
        seen.add(attempt)
        try:
            d = json.loads(attempt)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", attempt)
            if m:
                frag = m.group(0)
                if frag in seen:
                    continue
                seen.add(frag)
                try:
                    d = json.loads(frag)
                except json.JSONDecodeError:
                    continue
            else:
                continue
        return _normalize_eval_dict(d)
    return None


def _normalize_eval_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    dims_in = d.get("dimensions") or []
    dims: List[Dict[str, Any]] = []
    if isinstance(dims_in, list):
        for x in dims_in[:12]:
            if not isinstance(x, dict):
                continue
            sid = str(x.get("id") or "dim")[:40]
            dims.append(
                {
                    "id": sid,
                    "label": str(x.get("label") or sid)[:120],
                    "score": max(1, min(5, int(x.get("score") or 3))),
                    "rationale": str(x.get("rationale") or "")[:400],
                }
            )
    rec = str(d.get("recommendation") or "maybe").lower()
    if rec not in ("apply", "maybe", "skip"):
        rec = "maybe"
    stories = d.get("story_candidates") or []
    sc_out: List[Dict[str, str]] = []
    if isinstance(stories, list):
        for s in stories[:5]:
            if not isinstance(s, dict):
                continue
            sc_out.append(
                {
                    "id": str(s.get("id") or uuid.uuid4().hex)[:32],
                    "title": str(s.get("title") or "")[:120],
                    "situation": str(s.get("situation") or "")[:500],
                    "task": str(s.get("task") or "")[:500],
                    "action": str(s.get("action") or "")[:500],
                    "result": str(s.get("result") or "")[:500],
                    "reflection": str(s.get("reflection") or "")[:500],
                }
            )

    def _str_list(key: str, max_n: int) -> List[str]:
        v = d.get(key) or []
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if str(x).strip()][:max_n]

    try:
        overall = float(d.get("overall_score"))
        overall = max(1.0, min(5.0, overall))
    except (TypeError, ValueError):
        overall = 3.0

    return {
        "schema_version": SCHEMA_VERSION,
        "overall_score": overall,
        "dimensions": dims,
        "role_summary": str(d.get("role_summary") or "")[:4000],
        "cv_match": str(d.get("cv_match") or "")[:4000],
        "gaps": _str_list("gaps", 12),
        "level_strategy": str(d.get("level_strategy") or "")[:2000],
        "comp_notes": str(d.get("comp_notes") or "")[:2000],
        "personalization_hooks": _str_list("personalization_hooks", 12),
        "interview_prep": _str_list("interview_prep", 12),
        "story_candidates": sc_out,
        "recommendation": rec,
        "recommendation_rationale": str(d.get("recommendation_rationale") or "")[:3000],
    }


def _hint_block(cfg: JobShuntSettings) -> str:
    parts: List[str] = []
    if cfg.user_preferences:
        parts.append("Candidate preferences (respect in recommendation):\n" + "\n".join(f"- {p}" for p in cfg.user_preferences[:30]))
    hints = cfg.archetype_hints or []
    if hints:
        parts.append("Role archetypes / focus:\n" + "\n".join(f"- {h}" for h in hints[:20]))
    w = cfg.evaluation_dimension_weights or {}
    if w:
        parts.append("Dimension weight hints (higher = more important): " + json.dumps(w, ensure_ascii=False))
    return "\n\n".join(parts) if parts else ""


def build_evaluation(
    job_spec: str,
    resume_text: str,
    *,
    cfg: JobShuntSettings,
    use_llm: bool = True,
    max_out_tokens: int = 4500,
) -> Optional[Dict[str, Any]]:
    from .text_sanitize import sanitize_paste_artifacts

    job_spec = sanitize_paste_artifacts(job_spec or "")
    resume_text = sanitize_paste_artifacts(resume_text or "")
    if not use_llm or not (job_spec or "").strip():
        return None
    spec = (job_spec or "")[:24_000]
    resume = (resume_text or "")[:16_000]
    extra = _hint_block(cfg)
    user = (
        f"{extra}\n\n--- JOB POSTING ---\n{spec}\n\n--- RÉSUMÉ DRAFT (vault-based) ---\n{resume}\n"
        if extra
        else f"--- JOB POSTING ---\n{spec}\n\n--- RÉSUMÉ DRAFT (vault-based) ---\n{resume}\n"
    )
    try:
        raw = _llm_eval(_EVAL_SYSTEM, user, max_out_tokens=max_out_tokens)
    except Exception:
        return None
    return _parse_evaluation_json(raw)
