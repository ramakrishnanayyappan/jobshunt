"""LLM insights JSON normalization."""
from __future__ import annotations

from jobshunt.agents.jobshunt import insights


def test_parse_llm_insights_tagged_tips_and_gaps() -> None:
    raw = (
        '{"technical_skills":["Go"],"highlights":["a","b","c","d"],'
        '"gaps":[{"id":"g1","text":"missing k8s"}],"quick_tips":[{"text":"add metrics"}]}'
    )
    out = insights._parse_llm_insights(raw)
    assert out is not None
    assert out["gaps"] == [{"id": "g1", "text": "missing k8s"}]
    assert out["quick_tips"][0]["text"] == "add metrics"
    assert "id" in out["quick_tips"][0]


def test_build_insights_smoke_no_llm() -> None:
    payload = insights.build_insights("software engineer", "SUMMARY\nok\n", use_llm=False)
    assert "heuristic_ats" in payload
    assert payload["llm"] is None
