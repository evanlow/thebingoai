"""_parse_patterns — the seam the skill-detection credit void hangs on.

None means "unusable LLM output": the task voids the credit turn instead of
billing for garbage, so the None/list contract must hold exactly.
"""
from backend.tasks.skill_detection_tasks import _parse_patterns


def test_plain_json_array():
    assert _parse_patterns('[{"suggested_name": "a"}]') == [{"suggested_name": "a"}]


def test_markdown_fenced_array():
    fenced = '```json\n[{"suggested_name": "a"}]\n```'
    assert _parse_patterns(fenced) == [{"suggested_name": "a"}]


def test_garbage_returns_none():
    assert _parse_patterns("sorry, I cannot help with that") is None


def test_non_list_json_returns_none():
    assert _parse_patterns('{"suggested_name": "a"}') is None


def test_empty_array_is_valid():
    # Valid "no patterns found" outcome — billed, not voided.
    assert _parse_patterns("[]") == []
