"""Iterative heuristic + LLM passes to improve plain-text résumé ATS heuristics."""
from __future__ import annotations

from typing import Any, Dict, List

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings

from . import insights
from .tailor import SYSTEM as TAILOR_SYSTEM
from .text_sanitize import sanitize_paste_artifacts

_REFINE_EXTRA = """

Your task now is to REVISE the existing résumé below to fix ATS/heuristic issues listed.
Rules:
- Output ONLY the full revised résumé as plain UTF-8 text (same structure rules as above).
- Do NOT add markdown or code fences.
- Preserve factual content: do not invent employers, titles, degrees, dates, or metrics.
- You MAY: rewrap long lines (target under 120 chars where reasonable), replace smart quotes with ASCII quotes,
  normalize bullets, add missing ALL-CAPS section headers if content fits, tighten phrasing for keyword overlap
  using words from the JOB POSTING only where truthful.
- If a section is missing but you have no factual content for it, output the header with a minimal honest line
  (e.g. "See experience above") only if necessary; prefer leaving structure intact.
"""

def _llm_refine_once(job_spec: str, resume_text: str, issues_block: str, *, max_out_tokens: int = 6000) -> str:
    user = (
        f"JOB POSTING (for keyword alignment only):\n{(job_spec or '')[:14000]}\n\n"
        f"CURRENT RÉSUMÉ:\n{(resume_text or '')[:14000]}\n\n"
        f"ISSUES TO ADDRESS:\n{issues_block}\n\n"
        "Output the complete revised résumé only."
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
                system=TAILOR_SYSTEM + _REFINE_EXTRA,
                messages=[{"role": "user", "content": user}],
            )
            b0 = r.content[0]
            return b0.text if b0.type == "text" else str(b0)
        return chat_text_impl(
            a,
            [{"role": "user", "content": user}],
            TAILOR_SYSTEM + _REFINE_EXTRA,
            max_out_tokens,
        )

    return run_with_llm_fallback("jobshunt", _once)


def _strip_fence(t: str) -> str:
    s = (t or "").strip()
    if s.startswith("```"):
        lines = s.split("\n")
        lines = lines[1:] if lines else lines
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        s = "\n".join(lines).strip()
    return s


def _non_good_factors(heur: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in heur.get("factors") or []:
        if isinstance(f, dict) and f.get("status") != "good":
            out.append(f)
    return out


def refine_resume_for_ats(
    job_spec: str,
    resume_text: str,
    *,
    max_rounds: int = 3,
    max_out_tokens: int = 6000,
) -> Dict[str, Any]:
    job_spec = sanitize_paste_artifacts(job_spec or "")
    text = sanitize_paste_artifacts(resume_text or "")
    max_rounds = max(1, min(int(max_rounds), 6))
    rounds: List[Dict[str, Any]] = []

    for round_idx in range(max_rounds):
        heur = insights.heuristic_ats(job_spec, text)
        bad = _non_good_factors(heur)
        if not bad:
            rounds.append({"round": round_idx, "heuristic": heur, "edited": False})
            ins = insights.build_insights(job_spec, text, use_llm=False)
            return {
                "resume_text": text,
                "rounds": rounds,
                "final_heuristic": heur,
                "insights": ins,
                "stopped_reason": "all_good",
            }

        lines = []
        for f in bad:
            fid = f.get("id", "")
            label = f.get("label", "")
            detail = sanitize_paste_artifacts(str(f.get("detail") or ""))
            st = f.get("status", "")
            lines.append(f"- [{st}] {fid} / {label}: {detail}")
        issues_block = "\n".join(lines)

        try:
            raw = _llm_refine_once(job_spec, text, issues_block, max_out_tokens=max_out_tokens)
        except Exception as e:
            ins = insights.build_insights(job_spec, text, use_llm=False)
            rounds.append(
                {
                    "round": round_idx,
                    "heuristic": heur,
                    "edited": False,
                    "error": str(e),
                }
            )
            return {
                "resume_text": text,
                "rounds": rounds,
                "final_heuristic": heur,
                "insights": ins,
                "stopped_reason": "llm_error",
            }

        new_text = _strip_fence(raw)
        if not new_text.strip():
            rounds.append({"round": round_idx, "heuristic": heur, "edited": False, "error": "empty_model_output"})
            break

        text = new_text
        rounds.append({"round": round_idx, "heuristic": heur, "edited": True})

    heur = insights.heuristic_ats(job_spec, text)
    ins = insights.build_insights(job_spec, text, use_llm=False)
    return {
        "resume_text": text,
        "rounds": rounds,
        "final_heuristic": heur,
        "insights": ins,
        "stopped_reason": "max_rounds" if _non_good_factors(heur) else "all_good",
    }
