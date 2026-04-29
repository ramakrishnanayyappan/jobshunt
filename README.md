# JobShunt: AI-Powered Local Job Search & Resume Assistant.

## Overview

**JobShunt** is a **local** web app for organizing a job search around your own résumé materials and LLM providers. A **FastAPI** server and **React** UI run on your computer. You add API credentials and model choices in config; the app never requires a hosted SaaS backend.

Typical flow: set a **résumé vault** (directory or one file), capture a posting (**URL** or paste), then use the UI to **draft**, **evaluate**, **refine**, track applications in a **pipeline**, and **export** artifacts. Data stays under paths you control (YAML + JSON on disk).

### Capabilities

- **Evaluation (structured JSON)** — Overall score **1.0–5.0**, dimension rows **1–5** with short labels and rationales, narrative fields (role summary, vault match, gaps, interview prep, story candidates), and a machine suggestion **`apply` / `maybe` / `skip`** plus rationale. Output quality depends on your materials, the posting text, and the model.
- **Drafting** — Tailored draft from vault or optional **vault summary** plus job spec; optional **ATS-style refine** (rules + full-document LLM passes).
- **Fit & editing** — **Insights** (heuristics ± LLM), **apply selected insight lines**, **copilot** chat with workspace context.
- **Exports** — **TXT** always; **PDF/DOCX** with optional `export` install (`pip install -e ".[export]"`).
- **Pipeline** — Per-workspace rows (company, title, URL, status, scores, notes, run links).
- **Story bank** — STAR-style pins; optional bounded use inside drafts.
- **Batch** — Queue several jobs (server cap, commonly **15**); items run **one after another** in a background job with polling.
- **Scout (optional)** — **Playwright** visits URLs **you** list in YAML; collects **links** whose paths look like job postings (heuristic keywords such as `/jobs/`, and some ATS hostnames). Not a full ATS integration.
- **Outreach** — Template + LLM personalization; **copy only** from the UI.
- **Workspaces** — Separate summary, pipeline, batch, runs, and story bank per workspace.

Configuration paths and **secrets** belong in **your** machine only — see [Configuration](#configuration). Do not commit real `config.yaml` or keys; the repo ships **`config.example.yaml`** only.

---

## Responsible use

Outputs are **suggestions**. Review every draft and evaluation before you apply or send anything. The app does **not** submit applications for you unless you deliberately enable an optional local **apply-helper** script (disabled by default; run only code you trust).

---

## LLM setup in this app

Configure **saved profiles** and **agent routing** in the UI (`/settings/ai`). The JobShunt agent uses a **primary** profile and optional **fallbacks**. Features such as draft, evaluation, vault-summary merge, refine, insights, copilot, and negotiate all call your provider through the same local stack; no third-party “app cloud” is required beyond the APIs you choose.

---

## Getting useful results

Early runs can be vague if the vault or preferences are thin. Add solid résumé text, **preferences** / **archetype hints**, maintain an optional **vault summary**, and pin **stories** as you go. Large language models can still be wrong about facts — **check** employers, titles, and requirements yourself.

---

## Maturity

| Area | Status | Notes |
|------|--------|--------|
| Vault (folder/file, limits, macOS pickers) | **Stable** | PDF/DOCX inputs need `export` extra. Native pickers **macOS only**; elsewhere edit paths or YAML. |
| Vault summary | **Stable** | Optional; can block draft when manifest is stale. |
| Draft / compose | **Stable** | Vault or summary + job spec. |
| Insights + apply insight items | **Stable** | Sanitizes common paste noise from terminals. |
| Refine for ATS | **Stable** | Optional `auto_refine_after_draft`. |
| Copilot chat | **Stable** | Workspace-scoped; UI can confirm or auto-apply model actions. |
| Structured evaluation | **Stable** | Schema v1; config can weight dimensions. |
| Pipeline | **Stable** | JSON per workspace. |
| Story bank | **Stable** | Optional in draft. |
| Batch draft | **Stable** | Sequential worker; ~15 item cap. |
| Export TXT / PDF / DOCX | **Stable** | PDF/DOCX need `export` extra. |
| AI settings | **Stable** | Profiles + `jobshunt` agent bindings. |
| Scout | **Experimental** | `scout` extra + Playwright; opt-in; obey site rules. |
| Apply-helper subprocess | **Optional / advanced** | Gated in config; security-sensitive. |
| Multi-workspace | **Stable** | Registry + directories per workspace. |
| Multi-user / SSO / cloud sync | **Out of scope** | Single-user local design. |
| Auto-submit to employers | **Out of scope** | Manual copy or your own script only. |

---

## Table of contents

1. [Overview](#overview)
2. [Responsible use](#responsible-use)
3. [LLM setup in this app](#llm-setup-in-this-app)
4. [Getting useful results](#getting-useful-results)
5. [Maturity](#maturity)
6. [Requirements](#requirements)
7. [Install prerequisites (macOS, Linux, Windows)](#install-prerequisites-macos-linux-windows)
8. [Install JobShunt](#install-jobshunt)
9. [Build the web UI](#build-the-web-ui)
10. [Configuration](#configuration)
11. [Run](#run)
12. [First-time AI setup](#first-time-ai-setup)
13. [Feature reference (detailed)](#feature-reference-detailed)
14. [CLI reference](#cli-reference)
15. [Development](#development)
16. [Architecture](#architecture)
17. [Troubleshooting](#troubleshooting)
18. [Git repository](#git-repository)
19. [License](#license)

---

## Requirements

| Tool | Version | Role |
|------|---------|------|
| **Python** | 3.9+ | Backend API, CLI (`jobshunt`) |
| **Node.js** | 18+ (LTS recommended) | Build the React UI (`npm run build`) |
| **npm** | Bundled with Node | UI dependencies |

**Optional**

| Tool | Role |
|------|------|
| **Git** | Clone and update the repository |
| **Playwright** (via `scout` extra) | Experimental **portal scout** in a real browser |

---

## Install prerequisites (macOS, Linux, Windows)

### macOS

- **Python 3.9+**  
  - [python.org macOS installer](https://www.python.org/downloads/macos/), or Homebrew: `brew install python@3.12`  
  - Verify: `python3 --version`
- **Node.js 18+**  
  - [nodejs.org LTS](https://nodejs.org/), or Homebrew: `brew install node`  
  - Verify: `node --version`, `npm --version`

### Linux (Debian / Ubuntu and derivatives)

- **Python 3.9+**  
  - Example: `sudo apt update && sudo apt install python3 python3-venv python3-pip`  
  - Verify: `python3 --version`
- **Node.js 18+**  
  - Use [NodeSource](https://github.com/nodesource/distributions), **nvm**, **fnm**, or a distro package **only if** it provides Node ≥ 18.  
  - Verify: `node --version`, `npm --version`

### Linux (Fedora / RHEL-style)

- **Python:** `sudo dnf install python3` (or your distro’s Python 3.9+ package).  
- **Node:** Install Node 18+ via **nvm**, **NodeSource**, or equivalent if the default `nodejs` is too old.

### Windows

- **Python 3.9+**  
  - [python.org Windows installer](https://www.python.org/downloads/windows/) — check **“Add python.exe to PATH”**, or:  
  - `winget install Python.Python.3.12`  
  - Verify in **PowerShell** or **Command Prompt**: `py -3 --version` or `python --version`
- **Node.js 18+**  
  - [nodejs.org LTS Windows installer](https://nodejs.org/)  
  - Verify: `node --version`, `npm --version`

---

## Install JobShunt

From the **repository root** (the folder that contains `pyproject.toml`):

### Create a virtual environment (recommended)

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**Windows (cmd)**

```cmd
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
```

### Install the package

**Core + dev tests + résumé export libraries** (recommended):

```bash
pip install -e ".[dev,export]"
```

- **`export`**: adds **ReportLab**, **python-docx**, and **pypdf** so the app can read **PDF/DOCX** vault files and emit **PDF/DOCX exports**. Without it, some formats and export actions will tell you to install this extra.

**Optional scout (Playwright)**

```bash
pip install -e ".[scout]"
playwright install chromium
```

Use this only if you want the **portal scout** feature (browser automation). Respect each site’s terms and robots policies.

---

## Build the web UI

The FastAPI app serves the UI from **`src/jobshunt/static/ui/`** after a production build.

```bash
cd ui
npm ci
npm run build
cd ..
```

If you do not yet have a lockfile workflow, `npm install` instead of `npm ci` is fine.

**UI development** (optional): from `ui/`, `npm run dev` starts Vite with a proxy to `http://127.0.0.1:8765` — run **`jobshunt serve`** in another terminal so `/api` requests work.

---

## Configuration

### Where files live

| | macOS / Linux (default) | Windows (default) |
|--|-------------------------|-------------------|
| **Config** | `$XDG_CONFIG_HOME/jobshunt/config.yaml` (often `~/.config/jobshunt/config.yaml`) | `%APPDATA%\JobShunt\config.yaml` |
| **Data** | `$XDG_DATA_HOME/jobshunt` (often `~/.local/share/jobshunt`) | `%LOCALAPPDATA%\JobShunt\data` |

**Legacy paths** (`~/.config/jobhunt`, `~/.local/share/jobhunt`, `%…%\JobHunt`, **`JOBHUNT_HOME`**) are still used automatically when the newer **`jobshunt`** locations do not exist yet, so existing installs keep working without moving files.

**Override both** with environment variable **`JOBSHUNT_HOME`** (legacy **`JOBHUNT_HOME`** is also honored):

- Config: **`$JOBSHUNT_HOME/config.yaml`**
- Data: **`$JOBSHUNT_HOME/data/`**

On Windows, set `JOBSHUNT_HOME` via System Properties → Environment Variables, or for a single session in PowerShell:

```powershell
$env:JOBSHUNT_HOME = "C:\Users\You\jobshunt-data"
```

### Create your config

1. Print the path the app will use:

   ```bash
   jobshunt config-path
   ```

2. Copy **`config.example.yaml`** to that path (same filename **`config.yaml`**), then edit:

   - **`jobshunt.resume_vault_path`** — folder of résumés or one résumé file (`.txt`, `.md`, `.docx`, `.pdf` with optional deps).
   - **`jobshunt.output_path`** — optional explicit folder for exports; if empty, exports go under the app data tree (`…/jobshunt/exports` or the legacy `…/job_hunt/exports` if you still use an older data directory).
   - **`http.host` / `http.port`** — bind address (default `127.0.0.1:8765`).

Never commit **`config.yaml`** if it contains API keys or personal paths (this repo’s `.gitignore` already ignores common cases).

---

## Run

```bash
jobshunt serve
```

By default the CLI opens a browser to the UI at `http://127.0.0.1:8765/agents/jobshunt` when using default host and port (your values may differ).

If the UI was not built, visiting the root URL shows JSON with a hint to run `cd ui && npm install && npm run build`.

---

## First-time AI setup

JobShunt calls your LLM through **saved profiles** (not the raw “form only”):

1. Open **AI settings** in the UI (`/settings/ai`).
2. Enter provider, **Base URL**, **Model**, optional API key, then **save** a row under **My models (saved)**.
3. Under **JobShunt model**, choose **Primary** (and optional **Fallbacks**), then click **Save agent routing**.

Supported provider styles include OpenAI, Anthropic, Ollama, OpenAI-compatible proxies, and OpenRouter; path modes (`/v1/chat/completions`, responses-style paths, etc.) are configurable in the same screen.

---

## Feature reference (detailed)

Below is what the **JobShunt** UI and API support at a high level. All REST routes are under **`/api/agents/jobshunt/`** unless noted.

### Résumé vault

- **Folder or single file**: Config **`resume_vault_path`** can point to a directory (multiple résumés) or one file.
- **Formats**: Plain text / Markdown always; **PDF** and **DOCX** need `pip install -e ".[export]"` (and libraries noted in error messages if missing).
- **Limits**: **`max_vault_chars`** and **`max_vault_files`** avoid sending huge vaults to the model (see `config.example.yaml`).
- **Native folder/file pickers** are available **only on macOS** (`pick-vault-folder`, `pick-vault-file`, `pick-output-folder`). On Windows and Linux, type paths in settings or edit `config.yaml`.

### Vault summary (optional “master summary”)

When **`use_vault_summary_for_context`** is enabled, the app can maintain a **single condensed summary** of the vault plus a **manifest** of incorporated files to save tokens and surface **pending** changes.

- **Rescan** — detect new/changed vault files vs manifest.  
- **Rebuild / merge** — LLM-assisted update of the summary text.  
- **`block_draft_when_vault_summary_stale`** — can block drafting until pending files are merged (configurable).

Paths default under **`data/jobshunt/`**; **`vault_summary_path`** can override the summary file location.

### Workspace: job input, draft, insights, evaluation

- **Job URL or pasted posting** — Fetched or pasted content is normalized into a **job spec** for downstream steps.
- **Draft / compose** — Generates tailored résumé text using vault (or vault summary) + job context.
- **Insights** — Heuristic ATS-oriented signals plus optional LLM commentary (skills, gaps, tips). Job paste text is scrubbed of common **bracketed-paste** terminal noise before use.
- **Refine for ATS** — `POST /api/agents/jobshunt/refine-resume` runs up to several **heuristic → LLM full-résumé revise** rounds to clear non-good signals (line length, section headers, ASCII noise, etc.). Optional **`jobshunt.auto_refine_after_draft`** runs this automatically after each draft (extra LLM cost).
- **Apply insight items** — `POST /api/agents/jobshunt/apply-insight-items` merges selected **gaps / quick wins** into the current draft (one target section or per-item placement).
- **JobShunt copilot** — `POST /api/agents/jobshunt/chat` with `workspace_id`: workspace-aware assistant that returns **assistant_markdown** plus optional **client_actions** (`set_resume_text`, `set_job_paste`, `navigate_tab`) and can execute **refine** / **apply** on the server when the model emits the corresponding actions.
- **Evaluation** — **Structured** evaluation: dimensions, scores, role summary, match narrative, gaps, interview prep hints, story candidates, and a recommendation bucket — returned as structured JSON the UI renders.

### Application pipeline

- **CRUD** for pipeline rows: company, title, job URL, status (`new`, `evaluated`, `drafted`, `exported`, `applied`, `rejected`, `archived`), notes, scores, links to **run IDs**, etc.
- Stored locally per workspace under **`data/jobshunt/workspaces/<workspace_id>/pipeline.json`** (see **Workspaces**).

### Story bank

- **Pin** structured “stories” (STAR-style) derived from evaluations or edits.
- Optional inclusion in drafts when **`use_story_bank_in_draft`** is on.

### Negotiation / outreach

- **Templates** and **LLM-personalized** variants for recruiter or follow-up messages (copy from UI; no auto-send).

### Batch draft

- Queue **multiple applications** (cap enforced server-side, e.g. max 15) for draft generation; poll job status by **`job_id`**.

### Portal scout (optional)

- When **`scout_enabled`** and **`scout`** extra + Playwright browsers are installed, **POST `/scout`** can drive a browser session for supported flows.  
- Use responsibly and in line with site policies.

### Export

- **POST `/export`** produces run artifacts (e.g. Markdown/Text; **PDF/DOCX** with **`export`** extra) under the configured output / run layout.
- **GET `/runs`** and **GET `/download/{run_id}/{filename}`** list and download prior run files.

### Apply helper (advanced)

- **`apply_helper_script`** plus **`allow_apply_subprocess`** can run a user-defined helper (e.g. open a URL or a local tool). This is off by default; only enable scripts you trust.

### AI settings (global)

- **GET/PUT `/api/settings/ai`** — LLM profiles, API keys (stored locally in YAML), headers, temperature, token limits, OpenAI path vs gateway URL modes.
- **Per–JobShunt routing** — Primary/fallback profile IDs for the **`jobshunt`** agent only.

### Health

- **GET `/api/health`** — Liveness and version JSON.

---

## CLI reference

| Command | Description |
|---------|-------------|
| `jobshunt serve` | Start the API + static UI (opens browser). Options: `--host`, `--port` override config. |
| `jobshunt config-path` | Print resolved **`config.yaml`** path. |
| `jobshunt data-path` | Print resolved **data root** directory. |
| `jobshunt --version` | Show version. |

---

## Development

```bash
pip install -e ".[dev,export]"
pytest
```

Optional linting: **`ruff`** is included in **`dev`**.

---

## Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for package layout, routers, and data flow.

---

## Troubleshooting

- **`jobshunt: command not found`** — Activate your virtual environment and run `pip install -e .` again. With the venv active, the `jobshunt` console script should be on PATH (`Scripts` on Windows). If not, invoke the installed script by full path, e.g. `.venv/Scripts/jobshunt.exe` on Windows or `.venv/bin/jobshunt` on Unix.
- **Blank or JSON homepage** — Run **`npm run build`** in **`ui/`** so **`src/jobshunt/static/ui/`** exists.
- **404 on `/agents/...` after refresh** — Ensure you are on a recent build of `jobshunt.app` (SPA fallback serves `index.html` for client routes).
- **“Reading .pdf / .docx needs …”** — Install **`export`**: `pip install -e ".[export]"`.
- **Scout errors** — Install **`scout`** and run **`playwright install chromium`**.
- **400 / “No primary saved model”** — Complete [First-time AI setup](#first-time-ai-setup): saved profile + **Save agent routing**.
- **Port in use** — Change **`http.port`** in `config.yaml` or pass **`jobshunt serve --port …`**.

---

## Git repository

If this folder is not yet a Git repo, from the project root:

```bash
git init
git add -A
git commit -m "Initial commit: JobShunt local app"
```

`.gitignore` excludes virtualenvs, `node_modules`, local `config.yaml`, and generated `*.egg-info/` — only commit **`config.example.yaml`**, not secrets.

---

## License

MIT — see [LICENSE](LICENSE).
