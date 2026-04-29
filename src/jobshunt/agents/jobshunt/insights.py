from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings

_HEADERS = {
    "SUMMARY",
    "CORE COMPETENCIES",
    "EXPERIENCE",
    "EDUCATION",
    "CERTIFICATIONS & TRAINING",
}

_STOP = frozenset(
    "the a an and or for to of in on at with by from as is are was were be been being "
    "this that these those your our their will can may must should all any each one we you "
    "they it its if then than into out over under more most less least not no yes work team "
    "role job jobs position company years year experience skills strong excellent good ability "
    "able looking seeking apply application including include preferred plus etc"
    .split()
)

_LLM_SYSTEM = """You analyze a job posting and a finished résumé draft. Reply with ONE JSON object only, no markdown.
Keys (use exactly):
- "technical_skills": array of 8–15 distinct technical skills/tools/platforms inferred mainly from the JOB posting (strings).
- "highlights": array of exactly 4 short strings: why this résumé fits the role (concrete, no fluff).
- "gaps": array of 2–5 items; each item may be a string OR an object with "id" (short string) and "text" (the gap line).
- "quick_tips": array of 3–5 items; each may be a string OR an object with "id" and "text" (concise ATS edit).
Keep text under 140 characters per line. Valid JSON only."""


def _llm_completion(system: str, user: str, *, max_out_tokens: int) -> str:
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
                temperature=0.3,
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


def _normalize_tagged(items: Any, prefix: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(items, list):
        return out
    for i, x in enumerate(items):
        if isinstance(x, dict):
            tid = str(x.get("id") or "").strip() or f"{prefix}{i}"
            txt = str(x.get("text") or x.get("tip") or "").strip()
            if txt:
                out.append({"id": tid[:64], "text": txt[:500]})
        else:
            s = str(x).strip()
            if s:
                out.append({"id": f"{prefix}{i}", "text": s[:500]})
    return out[:20]


def _parse_llm_insights(raw: str) -> Optional[Dict[str, Any]]:
    t = _strip_code_fence(raw)
    for attempt in (t, re.sub(r"^```\w*\n|```$", "", t, flags=re.MULTILINE).strip()):
        if not attempt:
            continue
        try:
            d = json.loads(attempt)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}\s*$", attempt)
            if m:
                try:
                    d = json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
            else:
                continue
        skills = d.get("technical_skills") or []
        highlights = d.get("highlights") or []
        if isinstance(skills, list):
            skills = [str(x).strip() for x in skills if str(x).strip()][:20]
        else:
            skills = []
        if isinstance(highlights, list):
            highlights = [str(x).strip() for x in highlights if str(x).strip()][:10]
        else:
            highlights = []
        out = {
            "technical_skills": skills,
            "highlights": highlights,
            "gaps": _normalize_tagged(d.get("gaps"), "gap"),
            "quick_tips": _normalize_tagged(d.get("quick_tips"), "qt"),
        }
        return out
    return None


def _job_tokens(job_spec: str) -> List[str]:
    blob = job_spec.lower()
    words = re.findall(r"[a-z][a-z0-9+.#_-]{1,}", blob, re.I)
    out: List[str] = []
    for w in words:
        w = w.strip(".-,;:")
        if len(w) < 3 or w in _STOP:
            continue
        if w not in out:
            out.append(w)
    return out[:120]


def _resume_has_section(resume: str, header: str) -> bool:
    return bool(re.search(rf"^\s*{re.escape(header)}\s*$", resume, re.M))


def _experience_bullet_lines(resume: str) -> int:
    lines = resume.splitlines()
    in_exp = False
    n = 0
    for ln in lines:
        s = ln.strip()
        if s == "EXPERIENCE":
            in_exp = True
            continue
        if in_exp and s in _HEADERS and s != "EXPERIENCE":
            break
        if in_exp and s:
            if s.startswith("\u2022") or s.startswith("-") or s.startswith("*"):
                n += 1
    return n


def heuristic_ats(job_spec: str, resume_text: str) -> Dict[str, Any]:
    resume = resume_text or ""
    factors: List[Dict[str, Any]] = []
    score = 52

    present = [h for h in _HEADERS if _resume_has_section(resume, h)]
    miss = [h for h in _HEADERS if h not in present]
    if len(present) == 5:
        score += 22
        factors.append(
            {
                "id": "sections",
                "label": "Section structure",
                "status": "good",
                "detail": "All expected sections present (ATS-friendly plain layout).",
            }
        )
    elif present:
        score += 4 * len(present)
        factors.append(
            {
                "id": "sections",
                "label": "Section structure",
                "status": "warn",
                "detail": f"Missing: {', '.join(miss)} — parsers often expect clear section headings.",
            }
        )
    else:
        factors.append(
            {
                "id": "sections",
                "label": "Section structure",
                "status": "bad",
                "detail": "Required ALL-CAPS section headers not found.",
            }
        )

    toks = _job_tokens(job_spec)
    res_l = resume.lower()
    matched = sum(1 for t in toks if t in res_l)
    denom = max(12, min(len(toks), 50))
    overlap = int(round(100 * matched / denom))
    overlap = min(100, overlap)
    score += int(round(overlap * 0.22))
    if overlap >= 55:
        st = "good"
        det = f"~{matched} job keywords echoed in the résumé (estimated {overlap}% overlap)."
    elif overlap >= 35:
        st = "warn"
        det = "Moderate keyword overlap; weave a few more posting terms where truthful."
    else:
        st = "bad"
        det = "Low overlap with posting language; add relevant skills phrasing from the job."
    factors.append(
        {
            "id": "keywords",
            "label": "Keyword coverage",
            "status": st,
            "detail": det,
        }
    )

    bullets = _experience_bullet_lines(resume)
    if bullets >= 4:
        score += 10
        factors.append(
            {
                "id": "bullets",
                "label": "Experience bullets",
                "status": "good",
                "detail": f"{bullets} bullet lines detected under EXPERIENCE.",
            }
        )
    elif bullets >= 1:
        score += 5
        factors.append(
            {
                "id": "bullets",
                "label": "Experience bullets",
                "status": "warn",
                "detail": "Add more quantified bullets (metrics, scope) where possible.",
            }
        )
    else:
        factors.append(
            {
                "id": "bullets",
                "label": "Experience bullets",
                "status": "warn",
                "detail": "Few or no bullet lines under EXPERIENCE.",
            }
        )

    long_lines = [ln for ln in resume.splitlines() if len(ln) > 130]
    if not long_lines:
        score += 6
        factors.append(
            {
                "id": "line_length",
                "label": "Line length",
                "status": "good",
                "detail": "Lines are reasonably short for plain-text ATS parsing.",
            }
        )
    else:
        score -= 4
        factors.append(
            {
                "id": "line_length",
                "label": "Line length",
                "status": "warn",
                "detail": f"{len(long_lines)} very long lines — consider wrapping for readability/ATS.",
            }
        )

    if re.search(r"[^\x00-\x7F]", resume):
        score -= 3
        factors.append(
            {
                "id": "ascii",
                "label": "Special characters",
                "status": "warn",
                "detail": "Non-ASCII characters present; some parsers prefer plain ASCII in places.",
            }
        )

    score = max(18, min(100, int(score)))
    if score >= 82:
        tier = "Strong"
    elif score >= 68:
        tier = "Good"
    elif score >= 52:
        tier = "Fair"
    else:
        tier = "Needs work"

    return {
        "score": score,
        "tier": tier,
        "keyword_overlap_percent": overlap,
        "job_terms_sampled": len(toks),
        "factors": factors,
        "disclaimer": "Heuristic estimate only — real ATS vendors differ; use as a guide.",
    }


def llm_insights(job_spec: str, resume_text: str) -> Optional[Dict[str, Any]]:
    user = (
        "JOB POSTING / SPEC:\n"
        f"{(job_spec or '')[:14000]}\n\n"
        "RÉSUMÉ DRAFT:\n"
        f"{(resume_text or '')[:12000]}\n"
    )
    try:
        raw = _llm_completion(_LLM_SYSTEM, user, max_out_tokens=2000)
    except Exception:
        return None
    return _parse_llm_insights(raw)


def build_insights(
    job_spec: str,
    resume_text: str,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    from .text_sanitize import sanitize_paste_artifacts

    job_spec = sanitize_paste_artifacts(job_spec or "")
    resume_text = sanitize_paste_artifacts(resume_text or "")
    heur = heuristic_ats(job_spec, resume_text)
    llm_part: Optional[Dict[str, Any]] = None
    if use_llm and (resume_text or "").strip():
        llm_part = llm_insights(job_spec, resume_text)
    return {"heuristic_ats": heur, "llm": llm_part}
