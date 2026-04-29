"""Tests for evaluation JSON repair/normalization (no live LLM)."""
from __future__ import annotations

import json

from jobshunt.agents.jobshunt.evaluation import _parse_evaluation_json


def _minimal_valid() -> dict:
    return {
        "overall_score": 4.2,
        "dimensions": [
            {"id": "role_fit", "label": "Role fit", "score": 4, "rationale": "Strong alignment."}
        ],
        "role_summary": "Build widgets.",
        "cv_match": "You have widget experience.",
        "gaps": ["No Fortran"],
        "level_strategy": "Comfortable hire.",
        "comp_notes": "Verify comp; estimates may be wrong.",
        "personalization_hooks": ["Mention widgets"],
        "interview_prep": ["STAR: shipped widget v2"],
        "story_candidates": [{"title": "Widget launch", "situation": "S", "task": "T", "action": "A", "result": "R"}],
        "recommendation": "apply",
        "recommendation_rationale": "Good match.",
    }


def test_parse_plain_json():
    raw = json.dumps(_minimal_valid())
    out = _parse_evaluation_json(raw)
    assert out is not None
    assert out["schema_version"] == 1
    assert out["overall_score"] == 4.2
    assert out["dimensions"][0]["id"] == "role_fit"
    assert out["recommendation"] == "apply"
    assert len(out["story_candidates"]) == 1
    assert out["story_candidates"][0]["title"] == "Widget launch"


def test_parse_fenced_json():
    body = json.dumps(_minimal_valid())
    raw = "```json\n" + body + "\n```"
    out = _parse_evaluation_json(raw)
    assert out is not None
    assert out["overall_score"] == 4.2


def test_normalize_invalid_recommendation():
    d = _minimal_valid()
    d["recommendation"] = "strong maybe"
    out = _parse_evaluation_json(json.dumps(d))
    assert out is not None
    assert out["recommendation"] == "maybe"


def test_normalize_overall_score_clamped():
    d = _minimal_valid()
    d["overall_score"] = 99
    out = _parse_evaluation_json(json.dumps(d))
    assert out is not None
    assert out["overall_score"] == 5.0

    d["overall_score"] = 0
    out = _parse_evaluation_json(json.dumps(d))
    assert out is not None
    assert out["overall_score"] == 1.0


def test_trailing_garbage_object_extract():
    d = _minimal_valid()
    raw = "Here is JSON:\n" + json.dumps(d) + "\n\nThanks."
    out = _parse_evaluation_json(raw)
    assert out is not None
    assert out["role_summary"] == "Build widgets."


def test_parse_failure_returns_none():
    assert _parse_evaluation_json("not json") is None
    assert _parse_evaluation_json("") is None
