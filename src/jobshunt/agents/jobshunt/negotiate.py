"""Negotiation / outreach templates — copy-first; optional LLM personalization."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings

TEMPLATES: List[Dict[str, str]] = [
    {
        "id": "salary_counter",
        "title": "Salary discussion — ask for range first",
        "body": (
            "Hi {{hiring_manager_name}},\n\n"
            "Thank you for the conversation about the {{role_title}} role. I'm very interested in moving forward.\n\n"
            "To make sure we're aligned before the next step: could you share the approved salary band or "
            "compensation range for this position? That will help me evaluate fit alongside the scope and impact "
            "we discussed.\n\n"
            "Best,\n{{your_name}}"
        ),
    },
    {
        "id": "follow_up_after_chat",
        "title": "Follow-up after recruiter screen",
        "body": (
            "Hi {{recruiter_name}},\n\n"
            "Thanks again for walking me through the {{role_title}} opportunity at {{company}}. "
            "I'm particularly excited about {{one_hook}}.\n\n"
            "I'm happy to share any additional context or samples that would help the team evaluate my fit.\n\n"
            "Best,\n{{your_name}}"
        ),
    },
    {
        "id": "competing_offer_soft",
        "title": "Competing process — polite timing signal",
        "body": (
            "Hi {{contact_name}},\n\n"
            "I wanted to share a quick update: I'm in late-stage discussions with another firm and may need "
            "to make a decision by {{date_or_week}}. I'm still very interested in {{company}} — is it possible "
            "to align on next steps on your side within that window?\n\n"
            "Thank you,\n{{your_name}}"
        ),
    },
]


def list_templates() -> List[Dict[str, str]]:
    return [dict(x) for x in TEMPLATES]


_SYSTEM_PERSONALIZE = """You fill placeholders in a short outreach email template. Reply with ONE JSON object only:
{ "subject": "optional email subject line", "body": "the full email body with all placeholders replaced" }
Use professional, concise English. Do not invent job offers or compensation numbers not implied by context.
If a fact is unknown, use a brief neutral phrase or [TODO] rather than fabricating. Valid JSON only."""


def _llm(system: str, user: str, max_tokens: int = 1200) -> str:
    def _once(a: AISettings) -> str:
        if a.provider == "anthropic" and a.api_key:
            from anthropic import Anthropic

            cl = Anthropic(
                api_key=a.api_key,
                base_url=a.base_url or "https://api.anthropic.com",
            )
            m = a.model or "claude-3-5-haiku-20241022"
            cap = min(max_tokens, a.max_tokens, 4096)
            r = cl.messages.create(
                model=m,
                max_tokens=cap,
                temperature=0.35,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            b0 = r.content[0]
            return b0.text if b0.type == "text" else str(b0)
        return chat_text_impl(
            a,
            [{"role": "user", "content": user}],
            system,
            max_tokens,
        )

    return run_with_llm_fallback("jobshunt", _once)


def _strip_fence(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        t = "\n".join(lines).strip()
    return t


def personalize_template(
    template_id: str,
    *,
    context: Dict[str, Any],
    template_body_override: Optional[str] = None,
) -> Dict[str, str]:
    body = template_body_override
    if body is None:
        row = next((x for x in TEMPLATES if x["id"] == template_id), None)
        if not row:
            raise ValueError("unknown template_id")
        body = row["body"]
    ctx_json = json.dumps(context, ensure_ascii=False, indent=2)[:12000]
    user = (
        "TEMPLATE (replace {{placeholders}} from context; keep structure):\n"
        f"{body}\n\n"
        f"CONTEXT:\n{ctx_json}\n"
    )
    raw = _llm(_SYSTEM_PERSONALIZE, user, max_tokens=1200)
    t = _strip_fence(raw)
    try:
        d = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}\s*$", t)
        if not m:
            raise ValueError("model did not return JSON")
        d = json.loads(m.group(0))
    out_body = str(d.get("body") or "").strip()
    if not out_body:
        raise ValueError("empty body from model")
    subj = str(d.get("subject") or "").strip()
    return {"subject": subj, "body": out_body}
