"""Optional portal scout (Playwright). Off unless jobshunt.scout_enabled."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import yaml

from jobshunt.models import JobShuntSettings


def _validate_url(url: str) -> bool:
    try:
        p = urlparse((url or "").strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def run_scout(
    cfg: JobShuntSettings,
    portals_yaml: str,
    *,
    max_pages: int = 5,
    timeout_ms: int = 20000,
) -> List[Dict[str, Any]]:
    if not cfg.scout_enabled:
        raise PermissionError("scout_enabled is false in jobshunt settings — enable in config.yaml first")
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as e:
        raise ImportError(
            "Playwright not installed. pip install 'jobshunt[scout]' "
            "and run playwright install chromium"
        ) from e

    raw = yaml.safe_load(portals_yaml) or {}
    portals = raw.get("portals") or raw.get("sources") or raw
    if not isinstance(portals, list):
        portals = []
    urls_to_visit: List[str] = []
    for p in portals[:50]:
        if isinstance(p, str) and _validate_url(p):
            urls_to_visit.append(p.strip())
        elif isinstance(p, dict):
            u = p.get("url") or p.get("search_url")
            if isinstance(u, str) and _validate_url(u):
                urls_to_visit.append(u.strip())
    urls_to_visit = urls_to_visit[: max(1, min(max_pages, 20))]
    if not urls_to_visit:
        return []

    found: List[Dict[str, Any]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="JobShuntScout/1.0 (local)"
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        for u in urls_to_visit:
            try:
                page.goto(u, wait_until="domcontentloaded")
                for link in page.eval_on_selector_all(
                    "a[href]",
                    """els => els.map(e => ({ href: e.href, text: (e.innerText||'').trim().slice(0,120) }))""",
                ):
                    if not isinstance(link, dict):
                        continue
                    href = str(link.get("href") or "")
                    if not _validate_url(href):
                        continue
                    low = href.lower()
                    if any(x in low for x in ("/jobs/", "/job/", "/careers/", "greenhouse", "lever.co", "ashby")):
                        found.append(
                            {
                                "url": href[:2000],
                                "label": str(link.get("text") or "")[:200],
                                "source_page": u,
                            }
                        )
            except Exception as ex:
                found.append({"url": "", "error": str(ex)[:500], "source_page": u})
        context.close()
        browser.close()

    # Dedupe by url
    seen = set()
    out: List[Dict[str, Any]] = []
    for f in found:
        u = f.get("url") or ""
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(f)
    return out[:100]


def load_portals_file(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8")
