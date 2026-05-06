"""Native folder/file dialogs on Windows via PowerShell + WinForms (subprocess).

Used from FastAPI sync routes that run on a thread pool; COM UI must live in a
separate process with its own STA message loop.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional


def _ps_single_quote(s: str) -> str:
    """Single-quote a string for PowerShell (escape ' as '')."""
    return "'" + s.replace("'", "''") + "'"


def _run_powershell_ui(script_body: str) -> str:
    r = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Sta",
            "-WindowStyle",
            "Hidden",
            "-Command",
            script_body,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip() or "PowerShell dialog failed"
        raise RuntimeError(err)
    return (r.stdout or "").strip()


def pick_folder_windows(description: str) -> Optional[str]:
    """Show folder browser; return absolute path or None if cancelled."""
    desc = _ps_single_quote(description)
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.FolderBrowserDialog
$f.Description = {desc}
$f.ShowNewFolderButton = $true
[void]$f.ShowDialog()
if ($f.SelectedPath) {{ Write-Output $f.SelectedPath }}
"""
    out = _run_powershell_ui(script.strip())
    return out if out else None


def pick_open_file_windows(title: str, filter_line: str) -> Optional[str]:
    """Show open-file dialog; return absolute path or None if cancelled.

    filter_line: WinForms filter, e.g. "Resume files|*.txt;*.md;*.docx;*.pdf|All files|*.*"
    """
    t = _ps_single_quote(title)
    fl = _ps_single_quote(filter_line)
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$o = New-Object System.Windows.Forms.OpenFileDialog
$o.Title = {t}
$o.Filter = {fl}
$o.FilterIndex = 1
[void]$o.ShowDialog()
if ($o.FileName) {{ Write-Output $o.FileName }}
"""
    out = _run_powershell_ui(script.strip())
    return out if out else None


def normalize_picked_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def supported() -> bool:
    return sys.platform == "win32"
