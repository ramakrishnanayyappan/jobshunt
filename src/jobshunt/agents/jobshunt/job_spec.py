from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, List, Optional

import httpx

from .text_sanitize import sanitize_paste_artifacts

UA = "JobShuntLocal/1.0 (+https://jobshunt.ai/)"


def fetch_html(url: str, timeout: float = 45.0) -> str:
    r = httpx.get(
        url,
        headers={"User-Agent": UA},
        follow_redirects=True,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.text


def _strip_tags(html: str) -> str:
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _og_meta(html: str, prop: str) -> Optional[str]:
    m = re.search(
        rf'<meta\s+property=["\']{re.escape(prop)}["\']\s+content=["\']([^"\']*)["\']',
        html,
        re.I,
    )
    if m:
        return unescape(m.group(1).strip())
    m = re.search(
        rf'<meta\s+content=["\']([^"\']*)["\']\s+property=["\']{re.escape(prop)}["\']',
        html,
        re.I,
    )
    if m:
        return unescape(m.group(1).strip())
    return None


def _title_tag(html: str) -> Optional[str]:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not m:
        return None
    return unescape(re.sub(r"\s+", " ", m.group(1)).strip())


def _json_ld_job_postings(html: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.I | re.DOTALL,
    ):
        raw = m.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack = [data] if not isinstance(data, list) else list(data)
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                t = item.get("@type")
                types: List[str] = []
                if isinstance(t, str):
                    types = [t]
                elif isinstance(t, list):
                    types = [str(x) for x in t]
                if "JobPosting" in types:
                    out.append(item)
                for v in item.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(item, list):
                stack.extend(item)
    return out


def job_spec_from_html(html: str, source_url: str = "") -> str:
    lines: List[str] = []
    if source_url:
        lines.append(f"Source URL: {source_url}")

    for jp in _json_ld_job_postings(html):
        title = jp.get("title")
        if title:
            lines.append(f"Title: {title}")
        company = jp.get("hiringOrganization") or {}
        if isinstance(company, dict):
            name = company.get("name")
            if name:
                lines.append(f"Company: {name}")
        desc = jp.get("description")
        if isinstance(desc, str) and desc.strip():
            lines.append("Description (structured):")
            lines.append(_strip_tags(desc) if "<" in desc else desc.strip())
        loc = jp.get("jobLocation")
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality"),
                    addr.get("addressRegion"),
                    addr.get("addressCountry"),
                ]
                loc_s = ", ".join(str(p) for p in parts if p)
                if loc_s:
                    lines.append(f"Location: {loc_s}")
        emp = jp.get("employmentType")
        if emp:
            lines.append(f"Employment type: {emp}")

    og_t = _og_meta(html, "og:title")
    og_d = _og_meta(html, "og:description")
    if og_t and not any(l.startswith("Title:") for l in lines):
        lines.append(f"Title (OpenGraph): {og_t}")
    if og_d:
        lines.append("Summary (OpenGraph):")
        lines.append(og_d)

    tt = _title_tag(html)
    if tt and "Title:" not in "\n".join(lines):
        lines.append(f"Page title: {tt}")

    body = _strip_tags(html)
    if body:
        lines.append("\nPage text (excerpt):")
        lines.append(body[:12000])

    return sanitize_paste_artifacts("\n".join(lines).strip())


def job_spec_from_url(url: str) -> str:
    html = fetch_html(url)
    return job_spec_from_html(html, source_url=url)


def job_spec_from_paste(text: str) -> str:
    return sanitize_paste_artifacts((text or "").strip())
