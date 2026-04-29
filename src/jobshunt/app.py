from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jobshunt import __version__
from jobshunt.ai.resolve import AgentLLMNotConfigured
from jobshunt.ai.routes import router as ai_router
from jobshunt.agents.jobshunt.routes import router as jobshunt_router
from jobshunt.config import load_config

app = FastAPI(title="JobShunt (local)", version=__version__)


@app.exception_handler(AgentLLMNotConfigured)
async def _agent_llm_not_configured(_request: Request, exc: AgentLLMNotConfigured) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ai_router)
app.include_router(jobshunt_router)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "version": __version__, "app": "jobshunt-local"}


@app.get("/api/agents")
def list_agents() -> List[Dict[str, Any]]:
    return [
        {
            "id": "jobshunt",
            "name": "JobShunt",
            "description": "Tailor résumés from your vault to a job URL or pasted posting",
        },
    ]


def static_dir() -> Optional[Path]:
    d = load_config().http.static_dir
    if d:
        return Path(d).expanduser()
    p = Path(__file__).resolve().parent / "static" / "ui"
    if p.is_dir():
        return p
    return None


s = static_dir()
if s and s.is_dir():
    # React Router paths (e.g. /agents/jobshunt) are not files on disk. Starlette StaticFiles(html=True)
    # does not fall back to index.html for those URLs, so we mount /assets explicitly and serve index.html
    # for all other non-API GET paths.
    sr = s.resolve()
    assets_dir = sr / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="ui_assets")

    @app.get("/", include_in_schema=False)
    async def _spa_index() -> FileResponse:
        return FileResponse(sr / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api"):
            raise HTTPException(status_code=404)
        if ".." in full_path.split("/"):
            raise HTTPException(status_code=404)
        candidate = (sr / full_path).resolve()
        try:
            candidate.relative_to(sr)
        except ValueError:
            raise HTTPException(status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(sr / "index.html")
else:

    @app.get("/")
    def _no_ui() -> Dict[str, Any]:
        return {
            "name": "JobShunt (local)",
            "version": __version__,
            "hint": "Build UI: cd ui && npm install && npm run build",
            "api": "/api/health",
        }
