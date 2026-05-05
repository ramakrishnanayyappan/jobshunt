# JobsHunt unified installer entry (Windows). Bootstrap Python via winget if needed, then install.py.
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Installer = Join-Path $RepoRoot "install.py"

if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  Write-Host "[install] ERROR: pyproject.toml not found next to scripts/. Run from the JobsHunt repository."
  exit 1
}

function Test-Python39 {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return $true }
  }
  if (Get-Command python3 -ErrorAction SilentlyContinue) {
    & python3 -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return $true }
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return $true }
  }
  return $false
}

if (-not (Test-Python39)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "[install] Bootstrap: installing Python via winget (UAC may prompt)..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  }
}

if (-not (Test-Python39)) {
  Write-Host "[install] ERROR: Need Python 3.9+ (py -3, python3, or python). Install from python.org and re-run this script."
  exit 1
}

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 $Installer @args
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  & python3 $Installer @args
} else {
  & python $Installer @args
}
exit $LASTEXITCODE
