#!/usr/bin/env python3
"""Cross-platform JobsHunt installer: prerequisites, venv, pip, optional UI build."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Sequence


class ErrorCategory(str, Enum):
    PERMISSION = "permission"
    MISSING_PREREQ = "missing_prerequisite"
    NETWORK = "network"
    PACKAGE_MANAGER = "package_manager"
    UNSUPPORTED = "unsupported"
    GENERIC = "generic"


class InstallError(Exception):
    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        remediation: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.remediation = remediation or ""


def log(msg: str) -> None:
    print(f"[install] {msg}", flush=True)


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def pyproject_path() -> Path:
    return repo_root() / "pyproject.toml"


def static_ui_index() -> Path:
    return repo_root() / "src" / "jobshunt" / "static" / "ui" / "index.html"


def ui_dir() -> Path:
    return repo_root() / "ui"


def venv_dir(ctx: "Context") -> Path:
    return repo_root() / ctx.venv_name


def parse_py_version(s: str) -> Optional[tuple[int, int]]:
    s = s.strip()
    parts = s.split(".")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def py_ok(ver: tuple[int, int]) -> bool:
    return ver >= (3, 9)


def parse_node_major(version_str: str) -> Optional[int]:
    v = version_str.strip().lstrip("v")
    parts = v.split(".")
    if not parts:
        return None
    try:
        return int(parts[0])
    except ValueError:
        return None


def run_capture(
    argv: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(argv),
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        shell=False,
    )


def run_stream(argv: Sequence[str], *, cwd: Optional[Path] = None) -> None:
    p = subprocess.run(list(argv), cwd=str(cwd) if cwd else None, shell=False)
    if p.returncode != 0:
        raise InstallError(
            ErrorCategory.GENERIC,
            f"Command failed ({p.returncode}): {' '.join(argv)}",
            "Check the output above. Fix the reported issue and retry.",
        )


def classify_stderr(stderr: str, returncode: int) -> ErrorCategory:
    low = stderr.lower()
    if returncode != 0:
        if any(
            x in low
            for x in (
                "permission denied",
                "eacces",
                "access is denied",
                "requires elevation",
                "administrator",
                "operation not permitted",
            )
        ):
            return ErrorCategory.PERMISSION
        if any(
            x in low
            for x in (
                "network",
                "timed out",
                "connection refused",
                "could not resolve",
                "temporary failure",
            )
        ):
            return ErrorCategory.NETWORK
    return ErrorCategory.GENERIC


@dataclass
class Context:
    non_interactive: bool
    rebuild_ui: bool
    extras: str
    venv_name: str = ".venv"
    serve_after_install: bool = True
    serve_argv: list[str] = field(default_factory=list)
    manual_retry_cycles: int = 0
    max_manual_retries: int = 3
    transient_retries: int = 2

    def allow_input(self) -> bool:
        return not self.non_interactive


def detect_os() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def python_launcher_candidates(os_name: str) -> list[list[str]]:
    if os_name == "windows":
        found: list[list[str]] = []
        if shutil.which("py"):
            found.append(["py", "-3"])
        for exe in ("python3", "python"):
            if shutil.which(exe):
                found.append([exe])
        return found
    found = []
    for exe in ("python3", "python"):
        if shutil.which(exe):
            found.append([exe])
    return found


def get_python_version(prefix: list[str]) -> Optional[tuple[int, int]]:
    r = run_capture(
        [*prefix, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"]
    )
    if r.returncode != 0:
        return None
    return parse_py_version(r.stdout)


def resolve_bootstrap_python(os_name: str) -> tuple[list[str], tuple[int, int]]:
    for cand in python_launcher_candidates(os_name):
        ver = get_python_version(cand)
        if ver and py_ok(ver):
            return cand, ver
    raise InstallError(
        ErrorCategory.MISSING_PREREQ,
        "No suitable Python 3.9+ interpreter found on PATH.",
        _remediation_python(os_name),
    )


def _remediation_python(os_name: str) -> str:
    if os_name == "windows":
        return (
            "1) Install Python 3.12+ from https://www.python.org/downloads/windows/ "
            "(check 'Add to PATH'), or run PowerShell as Administrator and: "
            "winget install Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements\n"
            "2) Close and reopen the terminal, then run this installer again."
        )
    if os_name == "macos":
        return (
            "1) Install Python 3.9+ via https://www.python.org/downloads/macos/ or "
            "`brew install python@3.12` if you use Homebrew.\n"
            "2) Ensure `python3` is on your PATH, then run this installer again."
        )
    return (
        "1) Install Python 3.9+ (e.g. `sudo apt-get install -y python3 python3-venv python3-pip` on Debian/Ubuntu, "
        "or use pyenv if your distro ships an older default).\n"
        "2) Run this installer again."
    )


def _remediation_node(os_name: str) -> str:
    if os_name == "windows":
        return (
            "1) Install Node.js 18+ LTS from https://nodejs.org/ or: "
            "winget install OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements\n"
            "2) Reopen the terminal and run this installer again (or use --rebuild-ui after fixing)."
        )
    if os_name == "macos":
        return (
            "1) Install Node 18+ from https://nodejs.org/ or `brew install node`.\n"
            "2) Reopen terminal and run this installer again."
        )
    return (
        "1) Install Node.js 18+ (distro packages, NodeSource, nvm, or https://nodejs.org/).\n"
        "2) Run this installer again."
    )


def try_install_python_windows() -> None:
    winget = shutil.which("winget")
    if not winget:
        raise InstallError(
            ErrorCategory.PACKAGE_MANAGER,
            "winget not found; cannot auto-install Python.",
            "Enable App Installer / winget, or install Python from python.org, then retry.",
        )
    log("Installing Python via winget (may prompt UAC)...")
    r = run_capture(
        [
            winget,
            "install",
            "-e",
            "--id",
            "Python.Python.3.12",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    )
    if r.returncode != 0:
        cat = classify_stderr(r.stderr + r.stdout, r.returncode)
        raise InstallError(
            cat,
            f"winget install Python failed: {r.stderr or r.stdout}",
            "Try: open PowerShell as Administrator and re-run this installer, "
            "or install Python manually from https://www.python.org/downloads/windows/",
        )


def try_install_node_windows() -> None:
    winget = shutil.which("winget")
    if not winget:
        raise InstallError(
            ErrorCategory.PACKAGE_MANAGER,
            "winget not found; cannot auto-install Node.js.",
            _remediation_node("windows"),
        )
    log("Installing Node.js LTS via winget (may prompt UAC)...")
    r = run_capture(
        [
            winget,
            "install",
            "-e",
            "--id",
            "OpenJS.NodeJS.LTS",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    )
    if r.returncode != 0:
        cat = classify_stderr(r.stderr + r.stdout, r.returncode)
        raise InstallError(
            cat,
            f"winget install Node failed: {r.stderr or r.stdout}",
            _remediation_node("windows"),
        )


def try_install_python_macos() -> None:
    brew = shutil.which("brew")
    if not brew:
        raise InstallError(
            ErrorCategory.PACKAGE_MANAGER,
            "Homebrew not found; cannot auto-install Python on macOS.",
            _remediation_python("macos"),
        )
    log("Installing Python via Homebrew...")
    r = run_capture([brew, "install", "python@3.12"])
    if r.returncode != 0:
        cat = classify_stderr(r.stderr + r.stdout, r.returncode)
        raise InstallError(
            cat,
            f"brew install python failed: {r.stderr or r.stdout}",
            _remediation_python("macos"),
        )


def try_install_node_macos() -> None:
    brew = shutil.which("brew")
    if not brew:
        raise InstallError(
            ErrorCategory.PACKAGE_MANAGER,
            "Homebrew not found; cannot auto-install Node on macOS.",
            _remediation_node("macos"),
        )
    log("Installing Node via Homebrew...")
    r = run_capture([brew, "install", "node"])
    if r.returncode != 0:
        cat = classify_stderr(r.stderr + r.stdout, r.returncode)
        raise InstallError(
            cat,
            f"brew install node failed: {r.stderr or r.stdout}",
            _remediation_node("macos"),
        )


def _linux_has_apt() -> bool:
    return shutil.which("apt-get") is not None


def _linux_has_dnf() -> bool:
    return shutil.which("dnf") is not None


def try_install_python_linux() -> None:
    if _linux_has_apt():
        log("Installing Python via apt-get (requires sudo; may prompt for password)...")
        r = run_capture(["sudo", "apt-get", "update"])
        if r.returncode != 0:
            raise InstallError(
                classify_stderr(r.stderr, r.returncode),
                f"apt-get update failed: {r.stderr}",
                "Ensure sudo works, then retry. Or install python3, python3-venv, python3-pip manually.",
            )
        r = run_capture(
            [
                "sudo",
                "apt-get",
                "install",
                "-y",
                "python3",
                "python3-venv",
                "python3-pip",
            ]
        )
        if r.returncode != 0:
            raise InstallError(
                classify_stderr(r.stderr, r.returncode),
                f"apt-get install python failed: {r.stderr}",
                _remediation_python("linux"),
            )
        return
    if _linux_has_dnf():
        log("Installing Python via dnf (requires sudo)...")
        r = run_capture(["sudo", "dnf", "install", "-y", "python3"])
        if r.returncode != 0:
            raise InstallError(
                classify_stderr(r.stderr, r.returncode),
                f"dnf install python failed: {r.stderr}",
                _remediation_python("linux"),
            )
        return
    raise InstallError(
        ErrorCategory.UNSUPPORTED,
        "No supported Linux package manager (apt-get/dnf) found.",
        _remediation_python("linux"),
    )


def try_install_node_linux() -> None:
    if _linux_has_apt():
        log("Installing Node.js via apt (requires sudo)...")
        r = run_capture(["sudo", "apt-get", "install", "-y", "nodejs", "npm"])
        if r.returncode != 0:
            raise InstallError(
                classify_stderr(r.stderr, r.returncode),
                f"apt install nodejs failed: {r.stderr}",
                _remediation_node("linux"),
            )
        return
    if _linux_has_dnf():
        log("Installing Node.js via dnf (requires sudo)...")
        r = run_capture(["sudo", "dnf", "install", "-y", "nodejs", "npm"])
        if r.returncode != 0:
            raise InstallError(
                classify_stderr(r.stderr, r.returncode),
                f"dnf install nodejs failed: {r.stderr}",
                _remediation_node("linux"),
            )
        return
    raise InstallError(
        ErrorCategory.UNSUPPORTED,
        "No supported Linux package manager for Node install.",
        _remediation_node("linux"),
    )


def ensure_python(ctx: Context, os_name: str, *, auto_attempted: bool) -> tuple[list[str], tuple[int, int]]:
    try:
        return resolve_bootstrap_python(os_name)
    except InstallError as first:
        if auto_attempted:
            raise
        log(f"Could not find Python 3.9+: {first}. Attempting automatic install for {os_name}...")
        if os_name == "windows":
            try_install_python_windows()
        elif os_name == "macos":
            try_install_python_macos()
        elif os_name == "linux":
            try_install_python_linux()
        else:
            raise InstallError(
                ErrorCategory.UNSUPPORTED,
                f"Unsupported OS: {os_name}",
                _remediation_python(os_name),
            ) from first
        return resolve_bootstrap_python(os_name)


def get_node_major() -> Optional[int]:
    if not shutil.which("node"):
        return None
    r = run_capture(["node", "-p", "process.versions.node"])
    if r.returncode != 0:
        return None
    return parse_node_major(r.stdout)


def ensure_node(ctx: Context, os_name: str, *, auto_attempted: bool) -> None:
    major = get_node_major()
    if major is not None and major >= 18:
        return
    if auto_attempted:
        raise InstallError(
            ErrorCategory.MISSING_PREREQ,
            "Node.js 18+ required to build the UI but not found or too old.",
            _remediation_node(os_name),
        )
    log("Node.js 18+ missing; attempting automatic install...")
    if os_name == "windows":
        try_install_node_windows()
    elif os_name == "macos":
        try_install_node_macos()
    elif os_name == "linux":
        try_install_node_linux()
    else:
        raise InstallError(
            ErrorCategory.UNSUPPORTED,
            f"Cannot install Node automatically on {os_name}.",
            _remediation_node(os_name),
        )
    ensure_node(ctx, os_name, auto_attempted=True)


def ui_build_needed(ctx: Context) -> bool:
    if ctx.rebuild_ui:
        return True
    return not static_ui_index().is_file()


def venv_python_exe(ctx: Context) -> Path:
    d = venv_dir(ctx)
    if sys.platform == "win32":
        return d / "Scripts" / "python.exe"
    return d / "bin" / "python"


def jobshunt_console_script(ctx: Context) -> Path:
    d = venv_dir(ctx)
    if sys.platform == "win32":
        return d / "Scripts" / "jobshunt.exe"
    return d / "bin" / "jobshunt"


def run_jobshunt_serve(ctx: Context) -> int:
    exe = jobshunt_console_script(ctx)
    argv: list[str]
    if exe.is_file():
        argv = [str(exe), "serve", *ctx.serve_argv]
    else:
        log("Console script not found; using python -m jobshunt.cli serve")
        argv = [str(venv_python_exe(ctx)), "-m", "jobshunt.cli", "serve", *ctx.serve_argv]
    code = subprocess.run(argv, cwd=repo_root()).returncode
    hint = (
        "Server stopped. To relaunch without reinstalling: python3 install.py --serve-only"
        if sys.platform != "win32"
        else "Server stopped. To relaunch without reinstalling: py -3 install.py --serve-only"
    )
    log(hint)
    return code


def run_serve_only(ctx: Context) -> int:
    if not pyproject_path().is_file():
        print(
            f"[install] ERROR: pyproject.toml not found in {repo_root()}",
            file=sys.stderr,
        )
        return 1
    if not venv_python_exe(ctx).is_file():
        if sys.platform == "win32":
            hint = (
                "  py -3 install.py --install-only\n"
                "then:\n"
                "  py -3 install.py --serve-only"
            )
        else:
            hint = (
                "  python3 install.py --install-only\n"
                "then:\n"
                "  python3 install.py --serve-only"
            )
        print(
            "[install] No .venv found yet. Run a full install first, e.g.\n" + hint,
            file=sys.stderr,
        )
        return 1
    log("Relaunch (--serve-only): skipping install; starting jobshunt serve.")
    return run_jobshunt_serve(ctx)


def venv_pip(ctx: Context) -> list[str]:
    py = venv_python_exe(ctx)
    return [str(py), "-m", "pip"]


def ensure_venv(ctx: Context, bootstrap_prefix: list[str]) -> None:
    d = venv_dir(ctx)
    if venv_python_exe(ctx).is_file():
        log(f"Using existing virtual environment at {d}")
        return
    log(f"Creating virtual environment at {d}")
    run_stream([*bootstrap_prefix, "-m", "venv", str(d)])


def pip_install_project(ctx: Context) -> None:
    extras = ctx.extras.strip()
    spec = f".[{extras}]" if extras else "."
    log(f"Installing package in editable mode ({spec})...")
    run_stream([*venv_pip(ctx), "install", "-U", "pip"], cwd=repo_root())
    run_stream([*venv_pip(ctx), "install", "-e", spec], cwd=repo_root())


def run_with_transient_retry(ctx: Context, fn: Callable[[], None], label: str) -> None:
    last: Optional[BaseException] = None
    for attempt in range(ctx.transient_retries + 1):
        try:
            fn()
            return
        except InstallError as e:
            last = e
            if e.category != ErrorCategory.NETWORK or attempt >= ctx.transient_retries:
                raise
            wait = 2**attempt
            log(f"{label}: network issue, retrying in {wait}s ({attempt + 1}/{ctx.transient_retries + 1})...")
            time.sleep(wait)
    if last:
        raise last


def build_ui(ctx: Context) -> None:
    u = ui_dir()
    if not u.is_dir():
        raise InstallError(
            ErrorCategory.MISSING_PREREQ,
            f"UI directory missing: {u}",
            "Clone the full repository including the ui/ folder.",
        )
    lock = u / "package-lock.json"
    nm = u / "node_modules"
    if nm.is_dir() and ctx.manual_retry_cycles > 0:
        log("Cleaning ui/node_modules before retry...")
        shutil.rmtree(nm, ignore_errors=True)

    if lock.is_file():
        log("Running npm ci in ui/...")
        run_stream(["npm", "ci"], cwd=u)
    else:
        log("No package-lock.json; running npm install in ui/...")
        run_stream(["npm", "install"], cwd=u)
    log("Running npm run build in ui/...")
    run_stream(["npm", "run", "build"], cwd=u)


def print_next_steps(ctx: Context, os_name: str) -> None:
    root = repo_root()
    log("Install finished successfully.")
    if ctx.serve_after_install:
        log("Starting jobshunt serve (Ctrl+C to stop the server)...")
        print()
        return
    print()
    if os_name == "windows":
        print("Next steps — start the app (default install already runs serve; use these if you used --install-only):")
        print(f'  cd "{root}"')
        print("  py -3 install.py --serve-only")
        print()
        print("Or activate the venv, then:")
        print("  .\\.venv\\Scripts\\Activate.ps1")
        print("  jobshunt serve")
        print()
        print("Or Command Prompt:")
        print(f'  cd /d "{root}"')
        print("  .venv\\Scripts\\activate.bat")
        print("  jobshunt serve")
    else:
        print("Next steps — start the app (default install already runs serve; use these if you used --install-only):")
        print(f'  cd "{root}"')
        print("  python3 install.py --serve-only")
        print()
        print("Or:")
        print("  source .venv/bin/activate")
        print("  jobshunt serve")
    print()


def run_install_phases(ctx: Context) -> None:
    os_name = detect_os()
    if os_name == "other":
        raise InstallError(
            ErrorCategory.UNSUPPORTED,
            f"Unsupported platform: {sys.platform}",
            "Install Python 3.9+ manually, then run pip/venv steps from the README.",
        )

    if not pyproject_path().is_file():
        raise InstallError(
            ErrorCategory.GENERIC,
            f"pyproject.toml not found in {repo_root()}",
            "Run this script from the repository root (same folder as pyproject.toml).",
        )

    ni = os.environ.get("JOBSHUNT_INSTALL_NONINTERACTIVE", "").lower() in ("1", "true", "yes")
    ctx.non_interactive = ctx.non_interactive or ni

    log(f"Detected: {platform.system()} ({os_name}) — JobsHunt unified install")
    log(f"Repository root: {repo_root()}")

    bootstrap, pyver = ensure_python(ctx, os_name, auto_attempted=False)
    log(f"Using Python {pyver[0]}.{pyver[1]} via {' '.join(bootstrap)}")

    need_ui = ui_build_needed(ctx)
    if need_ui:
        log("UI build required (missing static bundle or --rebuild-ui).")
        ensure_node(ctx, os_name, auto_attempted=False)
        n = get_node_major()
        if n is not None:
            log(f"Using Node major version {n}")
    else:
        log("Prebuilt UI found; skipping Node.js and npm build.")

    ensure_venv(ctx, bootstrap)

    def do_pip() -> None:
        pip_install_project(ctx)

    run_with_transient_retry(ctx, do_pip, "pip install")

    if need_ui:

        def do_npm() -> None:
            build_ui(ctx)

        run_with_transient_retry(ctx, do_npm, "npm")

    print_next_steps(ctx, os_name)


def wait_for_retry(ctx: Context) -> bool:
    if not ctx.allow_input():
        return False
    if ctx.manual_retry_cycles >= ctx.max_manual_retries:
        log(f"Maximum manual retries ({ctx.max_manual_retries}) reached. Fix your environment and run again.")
        return False
    print()
    print("--- Install paused after an error ---")
    try:
        input("Press Enter after you have applied the fix above to retry this install...")
    except EOFError:
        return False
    ctx.manual_retry_cycles += 1
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install JobsHunt into .venv and start jobshunt serve by default. "
            "Use --install-only or --serve-only to change that behavior."
        ),
        epilog=(
            'Pass extra args to "jobshunt serve" after --, e.g.: '
            "install.py -- --port 8766"
        ),
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt for Enter on errors; exit with message and non-zero code.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--install-only",
        action="store_true",
        help="Only install dependencies; do not start jobshunt serve afterward.",
    )
    mode.add_argument(
        "--serve-only",
        action="store_true",
        help="Skip install and only run jobshunt serve (relaunch after you closed the app or terminal).",
    )
    parser.add_argument(
        "--rebuild-ui",
        action="store_true",
        help="Always rebuild the React UI (requires Node 18+).",
    )
    parser.add_argument(
        "--extras",
        default="dev,export",
        help='pip extras for editable install (default: "dev,export"). Use empty string for core only.',
    )
    parser.add_argument(
        "--venv",
        default=".venv",
        help="Virtual environment directory name (default: .venv).",
    )
    raw_argv = sys.argv[1:]
    serve_argv: list[str] = []
    if "--" in raw_argv:
        sep = raw_argv.index("--")
        serve_argv = raw_argv[sep + 1 :]
        raw_argv = raw_argv[:sep]
    args = parser.parse_args(raw_argv)

    ctx = Context(
        non_interactive=args.non_interactive,
        rebuild_ui=args.rebuild_ui,
        extras=args.extras,
        venv_name=args.venv,
        serve_after_install=not args.install_only,
        serve_argv=serve_argv,
    )

    if args.serve_only:
        return run_serve_only(ctx)

    while True:
        try:
            run_install_phases(ctx)
            if ctx.serve_after_install:
                return run_jobshunt_serve(ctx)
            return 0
        except InstallError as e:
            print(f"\n[install] ERROR [{e.category.value}]: {e}", file=sys.stderr)
            if e.remediation:
                print(f"\n{e.remediation}\n", file=sys.stderr)
            if ctx.non_interactive or not wait_for_retry(ctx):
                return 1


if __name__ == "__main__":
    raise SystemExit(main())
