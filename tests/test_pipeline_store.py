"""Pipeline store CRUD with isolated data_root."""
from __future__ import annotations

from pathlib import Path

import pytest

from jobshunt.agents.jobshunt import pipeline as pl


@pytest.fixture
def isolated_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    def _ws_dir(wid: str) -> Path:
        d = tmp_path / "workspaces" / wid
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(pl, "workspace_data_dir", _ws_dir)
    return tmp_path


def test_create_list_update_delete(isolated_pipeline: Path):
    wid = "default"
    assert pl.list_applications(wid) == []

    row = pl.create_application(
        wid,
        company="Acme",
        title="Eng",
        job_url="https://jobs.example/1",
    )
    assert row["id"]
    assert row["status"] == "new"
    assert row["company"] == "Acme"

    listed = pl.list_applications(wid)
    assert len(listed) == 1
    assert listed[0]["id"] == row["id"]

    upd = pl.update_application(
        wid,
        row["id"],
        {"status": "drafted", "notes": "Ready", "overall_score": 3.5, "run_id": "run-abc"},
    )
    assert upd is not None
    assert upd["status"] == "drafted"

    patched = pl.patch_status(wid, row["id"], "applied")
    assert patched is not None
    assert patched["status"] == "applied"

    assert pl.delete_application(wid, row["id"]) is True
    assert pl.list_applications(wid) == []


def test_patch_status_rejects_invalid(isolated_pipeline: Path):
    wid = "default"
    row = pl.create_application(wid, company="X", title="Y")
    assert pl.patch_status(wid, row["id"], "not_a_status") is None


def test_corrupt_file_falls_back_to_empty(isolated_pipeline: Path, monkeypatch: pytest.MonkeyPatch):
    wid = "default"

    def _ws_dir(wid_arg: str) -> Path:
        d = isolated_pipeline / "workspaces" / wid_arg
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(pl, "workspace_data_dir", _ws_dir)
    p = isolated_pipeline / "workspaces" / wid
    p.mkdir(parents=True, exist_ok=True)
    (p / "pipeline.json").write_text("{ not valid json", encoding="utf-8")
    assert pl.list_applications(wid) == []
