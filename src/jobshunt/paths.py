from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def _home_base() -> Optional[Path]:
    raw = (os.environ.get("JOBSHUNT_HOME") or os.environ.get("JOBHUNT_HOME") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def config_path(override: Optional[Path] = None) -> Path:
    if override is not None:
        return override
    hb = _home_base()
    if hb:
        return hb / "config.yaml"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        primary = (Path(appdata) / "JobShunt" / "config.yaml").resolve()
        legacy = (Path(appdata) / "JobHunt" / "config.yaml").resolve()
        if legacy.is_file() and not primary.is_file():
            return legacy
        return primary
    xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    primary = (Path(xdg) / "jobshunt" / "config.yaml").resolve()
    legacy = (Path(xdg) / "jobhunt" / "config.yaml").resolve()
    if legacy.is_file() and not primary.is_file():
        return legacy
    return primary


def data_root(override: Optional[Path] = None) -> Path:
    if override is not None:
        return override.resolve()
    hb = _home_base()
    if hb:
        p = hb / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        primary = (Path(local) / "JobShunt" / "data").resolve()
        legacy = (Path(local) / "JobHunt" / "data").resolve()
        if legacy.is_dir() and not primary.is_dir():
            p = legacy
        else:
            p = primary
    else:
        xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        primary = (Path(xdg) / "jobshunt").resolve()
        legacy = (Path(xdg) / "jobhunt").resolve()
        if legacy.is_dir() and not primary.is_dir():
            p = legacy
        else:
            p = primary
    p.mkdir(parents=True, exist_ok=True)
    return p
