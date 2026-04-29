"""Apply-insight-items input validation (no LLM)."""
from __future__ import annotations

import pytest

from jobshunt.agents.jobshunt import insight_apply


def test_apply_items_requires_section_for_same_section() -> None:
    with pytest.raises(ValueError, match="section"):
        insight_apply.apply_insight_items(
            "job",
            "SUMMARY\n\n",
            [{"id": "1", "text": "x"}],
            mode="same_section",
            section=None,
        )


def test_apply_items_empty_raises() -> None:
    with pytest.raises(ValueError, match="No items"):
        insight_apply.apply_insight_items(
            "job",
            "SUMMARY\n\n",
            [],
            mode="same_section",
            section="SUMMARY",
        )
