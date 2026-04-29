"""Vault summary manifest / pending detection (no LLM)."""
from __future__ import annotations

from pathlib import Path

import pytest

from jobshunt.agents.jobshunt import vault_summary as vs
from jobshunt.models import JobShuntSettings


@pytest.fixture
def isolated_vs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(vs, "jobshunt_data_dir", lambda _wid: tmp_path)
    return tmp_path


def test_pending_detects_new_file(isolated_vs: Path, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "r.txt").write_text("Role A at Co", encoding="utf-8")
    pend = vs.list_pending_vault_files(vault, JobShuntSettings(), "default")
    assert len(pend) == 1
    assert pend[0]["reason"] == "new"


def test_pending_clear_after_manifest_record(isolated_vs: Path, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "r.txt"
    f.write_text("hello", encoding="utf-8")
    mtime_ns, chash = vs._fingerprint(f)
    manifest = {
        "schema_version": vs.MANIFEST_VERSION,
        "updated_at": "",
        "files": [
            {
                "path": str(f.resolve()),
                "display_name": "r.txt",
                "mtime_ns": mtime_ns,
                "content_sha256": chash,
                "incorporated_at": "x",
            }
        ],
    }
    import json

    (isolated_vs / "vault_summary_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    pend = vs.list_pending_vault_files(vault, JobShuntSettings(), "default")
    assert pend == []


def test_pending_on_content_change(isolated_vs: Path, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "r.txt"
    f.write_text("v1", encoding="utf-8")
    mtime_ns, chash = vs._fingerprint(f)
    manifest = {
        "schema_version": vs.MANIFEST_VERSION,
        "updated_at": "",
        "files": [
            {
                "path": str(f.resolve()),
                "display_name": "r.txt",
                "mtime_ns": mtime_ns,
                "content_sha256": "wrong",
                "incorporated_at": "x",
            }
        ],
    }
    import json

    (isolated_vs / "vault_summary_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    pend = vs.list_pending_vault_files(vault, JobShuntSettings(), "default")
    assert len(pend) == 1
    assert pend[0]["reason"] == "modified"


def test_merge_pending_no_work(isolated_vs: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    cfg = JobShuntSettings(vault_summary_path=str(tmp_path / "sum.txt"))
    monkeypatch.setattr(vs, "jobshunt_data_dir", lambda _wid: isolated_vs)
    out = vs.merge_pending(vault, cfg, "default", only_pending=True)
    assert out["ok"] is True
    assert out["merged"] == 0


def test_vault_text_bundle_mode(isolated_vs: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.txt").write_text("Engineer at X", encoding="utf-8")
    cfg = JobShuntSettings(use_vault_summary_for_context=False)
    monkeypatch.setattr(vs, "jobshunt_data_dir", lambda _wid: isolated_vs)
    txt, used, label = vs.vault_text_for_tailor(vault, cfg, "default")
    assert label == "bundle"
    assert "Engineer" in txt
    assert len(used) >= 1
