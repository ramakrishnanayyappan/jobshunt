from __future__ import annotations

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings


SYSTEM = """You are an expert résumé writer. Produce a tailored résumé as plain UTF-8 text ONLY.

Strict format (no markdown, no code fences):
- Line 1: candidate full name exactly as they use professionally.
- Line 2: single contact line (email, phone, city as appropriate).
- Line 3: blank.
- Then sections in this exact order, each header alone on its own line in ALL CAPS:
  SUMMARY
  CORE COMPETENCIES
  EXPERIENCE
  EDUCATION
  CERTIFICATIONS & TRAINING
- Under EXPERIENCE: each role starts with a non-bullet line "Title | Company | Location | Dates".
  Achievements as bullet lines starting with • or -.
- Under CORE COMPETENCIES: comma-separated or short lines; keep scannable.
- Tailor wording to the job posting; do not invent employers, degrees, or credentials not supported by the source résumés.
- If the vault material is thin, still output valid structure; you may generalize carefully.

Output nothing before the name and nothing after the last section content."""


def compose_resume_text(
    job_spec: str,
    vault_text: str,
    *,
    title_case_name: bool = True,
    max_out_tokens: int = 6000,
    story_bank_context: str = "",
) -> str:
    vault_block = vault_text.strip() or "(no vault files matched; infer minimal structure from job only)"
    extra = (story_bank_context or "").strip()
    user_parts = [
        "Job posting / spec:\n" + job_spec.strip(),
        "Source résumé material (vault):\n" + vault_block,
    ]
    if extra:
        user_parts.append(extra)
    user = "\n\n".join(user_parts) + "\n"
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
                temperature=a.temperature,
                system=SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            b0 = r.content[0]
            return b0.text if b0.type == "text" else str(b0)
        return chat_text_impl(
            a,
            [{"role": "user", "content": user}],
            SYSTEM,
            max_out_tokens,
        )

    raw = run_with_llm_fallback("jobshunt", _once)
    t = raw.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines.pop()
        t = "\n".join(lines).strip()

    if title_case_name and t:
        parts = t.split("\n", 1)
        nm = parts[0].strip()
        if nm:
            t = nm.title() + ("\n" + parts[1] if len(parts) > 1 else "")

    return t
