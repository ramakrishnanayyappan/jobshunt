"""Paste / OSC artifact cleanup."""
from __future__ import annotations

from jobshunt.agents.jobshunt.text_sanitize import sanitize_paste_artifacts


def test_sanitize_bracketed_paste_literal() -> None:
    s = "[200~hello[201~"
    assert sanitize_paste_artifacts(s) == "hello"


def test_sanitize_esc_bracketed_paste() -> None:
    s = "\x1b[200~x\x1b[201~"
    assert sanitize_paste_artifacts(s) == "x"


def test_sanitize_bel() -> None:
    assert sanitize_paste_artifacts("a\x07b") == "ab"
