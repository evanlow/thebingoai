"""Dashboard agent prompt is locked to BigQuery dialect.

Widget SQL always executes against the DataPlane = BigQuery in enterprise
lockdown. The generator MUST emit BigQuery; Postgres idioms like `::cast`,
`AT TIME ZONE`, `INTERVAL 'N day'`, and `DATE_TRUNC('day', col)` fail at
BigQuery execution. This module locks the contract.
"""
from unittest.mock import patch

import pytest

from backend.agents import profile_defaults
from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt
from backend.agents.profile_defaults import (
    BIGQUERY_DIALECT_HINTS,
    SQLITE_DIALECT_HINTS,
    get_default_section,
)


_BQ_REQUIRED_TOKENS = (
    "backticks",
    "CAST(x AS TYPE)",
    "DATE_TRUNC(x, DAY)",
    "INTERVAL N UNIT",
    "TIMESTAMP_TRUNC",
    "DATE_SUB",
    "LOWER(col) LIKE LOWER(pattern)",
)


def test_bigquery_hints_contain_critical_syntax_rules():
    """Smoke-check that a future copy edit doesn't silently drop the rules
    that caused the original bug."""
    for token in _BQ_REQUIRED_TOKENS:
        assert token in BIGQUERY_DIALECT_HINTS, (
            f"BIGQUERY_DIALECT_HINTS missing required syntax rule: {token!r}"
        )


@pytest.mark.parametrize("csv_loaded,bq_loaded", [
    (False, False),
    (True, False),
    (False, True),
    (True, True),
])
def test_dashboard_prompt_always_has_bigquery_hints(csv_loaded, bq_loaded):
    """BQ hints appended regardless of plugin-loaded flags."""
    with patch.object(profile_defaults, "_csv_plugin_loaded", return_value=csv_loaded), \
         patch.object(profile_defaults, "_bigquery_plugin_loaded", return_value=bq_loaded):
        prompt = build_dashboard_agent_prompt(available_connections=[1])
    assert BIGQUERY_DIALECT_HINTS in prompt


def test_dashboard_prompt_never_contains_sqlite_hints():
    """SQLite hints must not leak in even when CSV plugin is reported loaded.

    CSV uploads write to DataPlane (Parquet → BQ in lockdown). SQLite SQL
    against a BQ data plane fails.
    """
    with patch.object(profile_defaults, "_csv_plugin_loaded", return_value=True), \
         patch.object(profile_defaults, "_bigquery_plugin_loaded", return_value=True):
        prompt = build_dashboard_agent_prompt(available_connections=[1])
    assert SQLITE_DIALECT_HINTS not in prompt


def test_get_default_section_dashboard_tools_locks_to_bigquery():
    """Profile-defaults helper also returns BQ-only hints for dashboard_agent."""
    with patch.object(profile_defaults, "_csv_plugin_loaded", return_value=True), \
         patch.object(profile_defaults, "_bigquery_plugin_loaded", return_value=False):
        content = get_default_section("dashboard_agent", "tools")
    assert content is not None
    assert BIGQUERY_DIALECT_HINTS in content
    assert SQLITE_DIALECT_HINTS not in content
