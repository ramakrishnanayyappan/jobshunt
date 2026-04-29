"""Workspace-aware chat: JSON tool protocol + server-side tool execution."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from jobshunt.ai.client import chat_text_impl, run_with_llm_fallback
from jobshunt.models import AISettings

from . import insight_apply, resume_refine
from .text_sanitize import sanitize_paste_artifacts

_CHAT_SYSTEM = """You are Job Hunt Copilot for a local-first résumé / job-search app.

Tabs: Workspace (vault paths, vault summary, career prefs), Pipeline (résumé draft editor + export),
Fit & ATS (match insights, evaluation), Stories & outreach, Batch, Scout.
Each workspace has its own pipeline data, story bank, batch jobs, and vault summary; API uses workspace_id.

Reply with ONE JSON object only, no markdown fences:
{
  "assistant_markdown": "string (ok to use **bold** or bullet lines; keep practical)",
  "client_actions": [ ... optional; default [] ]
}

Allowed client_actions (each is one object):
- {"type":"set_resume_text","resume_text":"full plain-text résumé"} — only when user clearly wants replacement text
- {"type":"set_job_paste","job_text":"raw job description"}
- {"type":"navigate_tab","tab":"workspace"} — tab one of: workspace, pipeline, fit, stories, batch, scout
- {"type":"request_refine_resume","max_rounds":3} — asks server to run ATS fix-loop on current résumé
- {"type":"request_apply_insight_items","items":[{"id":"qt0","text":"..."}],"mode":"same_section","section":"SUMMARY"}
  or mode per_item with items only; section must be one of: SUMMARY, CORE COMPETENCIES, EXPERIENCE, EDUCATION, CERTIFICATIONS & TRAINING

Rules: Do not invent employers, degrees, or interviews. Prefer short answers. If unsure, ask in assistant_markdown and leave client_actions empty.
"""


def _strip_fence(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        lines = lines[1:] if lines else lines
        while lines and lines[-1].strip().startswith("```"):
            lines.pop()
        t = "\n".join(lines).strip()
    return t


def _parse_chat_json(raw: str) -> Optional[Dict[str, Any]]:
    t = _strip_fence(raw)
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
        if isinstance(d, dict) and "assistant_markdown" in d:
            return d
    return None


def _chat_llm(system: str, user: str, *, max_out_tokens: int = 3500) -> str:
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
            max_out_tokens,
        )

    return run_with_llm_fallback("jobshunt", _once)


def _validate_actions(actions: Any) -> List[Dict[str, Any]]:
    if not isinstance(actions, list):
        return []
    allowed = {
        "set_resume_text",
        "set_job_paste",
        "navigate_tab",
        "request_refine_resume",
        "request_apply_insight_items",
    }
    out: List[Dict[str, Any]] = []
    for a in actions[:12]:
        if not isinstance(a, dict):
            continue
        t = str(a.get("type") or "").strip()
        if t in allowed:
            out.append(a)
    return out


def run_chat_turn(
    *,
    messages: List[Dict[str, str]],
    workspace_id: str,
    resume_text: str,
    job_spec: str,
    status_blob: Dict[str, Any],
    last_insights: Optional[Dict[str, Any]] = None,
    last_evaluation: Optional[Dict[str, Any]] = None,
    max_out_tokens: int = 3500,
) -> Dict[str, Any]:
    resume_text = sanitize_paste_artifacts(resume_text or "")
    job_spec = sanitize_paste_artifacts(job_spec or "")

    hist: List[str] = []
    for m in messages[-24:]:
        role = str(m.get("role") or "").strip().lower()
        content = sanitize_paste_artifacts(str(m.get("content") or ""))
        if role in ("user", "assistant") and content:
            hist.append(f"{role.upper()}: {content[:8000]}")

    extra = ""
    if last_insights is not None:
        extra += "\nLAST_INSIGHTS_JSON:\n" + json.dumps(last_insights, ensure_ascii=False)[:12000] + "\n"
    if last_evaluation is not None:
        extra += "\nLAST_EVALUATION_JSON:\n" + json.dumps(last_evaluation, ensure_ascii=False)[:12000] + "\n"

    user = (
        f"workspace_id: {workspace_id}\n"
        f"STATUS_SUMMARY_JSON:\n{json.dumps(status_blob, ensure_ascii=False)[:8000]}\n\n"
        f"CURRENT_JOB_SPEC (may be empty):\n{job_spec[:12000]}\n\n"
        f"CURRENT_RESUME_DRAFT:\n{resume_text[:12000]}\n"
        f"{extra}\n"
        "CONVERSATION:\n" + "\n\n".join(hist)
    )

    raw = _chat_llm(_CHAT_SYSTEM, user, max_out_tokens=max_out_tokens)
    parsed = _parse_chat_json(raw)
    if not parsed:
        return {
            "assistant_markdown": "Could not parse model response. Try a shorter message.",
            "client_actions": [],
            "tool_results": [],
            "parse_error": True,
        }

    assistant_markdown = str(parsed.get("assistant_markdown") or "").strip() or "(empty)"
    client_actions = _validate_actions(parsed.get("client_actions"))

    tool_results: List[Dict[str, Any]] = []
    passthrough: List[Dict[str, Any]] = []

    for act in client_actions:
        t = act.get("type")
        if t == "request_refine_resume":
            try:
                mr = int(act.get("max_rounds") or 3)
            except (TypeError, ValueError):
                mr = 3
            try:
                rr = resume_refine.refine_resume_for_ats(job_spec, resume_text, max_rounds=mr)
                tool_results.append({"type": "refine_resume", "ok": True, "result": rr})
                resume_text = rr["resume_text"]
            except Exception as e:
                tool_results.append({"type": "refine_resume", "ok": False, "error": str(e)})
        elif t == "request_apply_insight_items":
            items = act.get("items") or []
            mode = act.get("mode") or "same_section"
            sec = act.get("section")
            if mode not in ("same_section", "per_item"):
                tool_results.append(
                    {"type": "apply_insight_items", "ok": False, "error": "invalid mode"}
                )
                continue
            try:
                ar = insight_apply.apply_insight_items(
                    job_spec,
                    resume_text,
                    items if isinstance(items, list) else [],
                    mode=mode,
                    section=str(sec) if sec else None,
                )
                tool_results.append({"type": "apply_insight_items", "ok": True, "result": ar})
                resume_text = ar["resume_text"]
            except Exception as e:
                tool_results.append({"type": "apply_insight_items", "ok": False, "error": str(e)})
        else:
            passthrough.append(act)

    return {
        "assistant_markdown": assistant_markdown,
        "client_actions": passthrough,
        "tool_results": tool_results,
        "suggested_resume_text": resume_text if resume_text else None,
        "parse_error": False,
    }
