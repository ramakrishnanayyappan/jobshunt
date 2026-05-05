# -*- mode: python ; coding: utf-8 -*-
"""Build a desktop bundle: onedir + JobsHunt.app (macOS) or JobsHunt.exe (Windows).

Run from the developer machine (with jobshunt + dev deps installed):

  cd packaging/pyinstaller
  pip install pyinstaller
  pip install -e "../..[dev,export]"
  (cd ../../ui && npm ci && npm run build)
  pyinstaller jobshunt.spec

Outputs:
  dist/JobsHunt/           — folder with JobsHunt (+ _internal on PyInstaller 6+)
  dist/JobsHunt.app/      — macOS only; drag into /Applications

Icons: packaging/icons/JobsHunt.icns (macOS bundle), JobsHunt.ico (Windows EXE).

Release assets on GitHub (stable names for “latest” links): JobsHunt-mac.dmg, JobsHunt-Setup.exe.

Windows: compile packaging/windows/JobsHunt.iss with Inno Setup to install under Program Files
and add a Start Menu shortcut.
"""
# pyinstaller injects SPEC (path to this file) into the spec namespace.
from pathlib import Path

try:
    _spec = Path(SPEC).resolve()
except NameError as e:
    raise RuntimeError("This file must be run with PyInstaller, e.g. pyinstaller jobshunt.spec") from e

SPEC_DIR = _spec.parent
REPO_ROOT = SPEC_DIR.parents[1]
ICON_DIR = REPO_ROOT / "packaging" / "icons"
ICON_ICNS = ICON_DIR / "JobsHunt.icns"
ICON_ICO = ICON_DIR / "JobsHunt.ico"
ENTRY = SPEC_DIR / "entry_serve.py"
SRC_JOBSHUNT = REPO_ROOT / "src" / "jobshunt"
SRC_ROOT = REPO_ROOT / "src"

import sys

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.building.osx import BUNDLE

block_cipher = None

added_binaries = []
added_datas = [(str(SRC_JOBSHUNT / "static"), "jobshunt/static")]

try:
    from PyInstaller.utils.hooks import collect_all

    for pkg in (
        "uvicorn",
        "starlette",
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "httpx",
        "httpcore",
        "h11",
        "openai",
        "anthropic",
        "anyio",
        "click",
        "watchfiles",
        "yaml",
        "jinja2",
        "reportlab",
        "docx",
        "pypdf",
    ):
        try:
            datas, binaries, hiddenimports = collect_all(pkg)
            added_datas.extend(datas)
            added_binaries.extend(binaries)
        except ImportError:
            pass
except ImportError:
    pass

hiddenimports = [
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.loops.auto",
    "uvicorn.logging",
    "websockets",
    "websockets.extensions",
    "websockets.legacy",
    "watchfiles",
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC_ROOT)],
    binaries=added_binaries,
    datas=added_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_exe_icon = str(ICON_ICO) if sys.platform == "win32" and ICON_ICO.is_file() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JobsHunt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JobsHunt",
)

if sys.platform == "darwin":
    _bundle_icon = str(ICON_ICNS) if ICON_ICNS.is_file() else None
    app = BUNDLE(
        coll,
        name="JobsHunt.app",
        icon=_bundle_icon,
        bundle_identifier="ai.jobshunt.desktop",
        info_plist={
            "CFBundleName": "JobsHunt",
            "CFBundleDisplayName": "JobsHunt",
            "CFBundleExecutable": "JobsHunt",
            "CFBundlePackageType": "APPL",
            "CFBundleSignature": "????",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
