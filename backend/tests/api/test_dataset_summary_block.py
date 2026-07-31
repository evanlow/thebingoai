"""The orchestrator's dataset block is a routing summary, not a data dictionary.

Handing the orchestrator every column name, type and glossary description let it
answer "tell me more about this dataset" by paraphrasing the schema instead of
querying it — a complete-looking answer with no data behind it. The agents that
write SQL build their own full-schema blocks, so the orchestrator gets counts only.
"""
from types import SimpleNamespace

from backend.api.websocket import _render_dataset_summary


def _conn(**kw):
    return SimpleNamespace(source_filename="HR_dataset.csv", name="HR_dataset", **kw)


_CONTEXT = {
    "tables": {
        "csv_98": {
            "rowCount": 15000,
            "description": "Employee HR and performance dataset.",
            "columns": {
                "satisfaction_level": {
                    "type": "float",
                    "role": "measure",
                    "displayName": "Satisfaction Level",
                    "description": "Employee-reported satisfaction.",
                },
                "unnamed_11": {"type": "float", "role": "measure"},
                "salary": {"type": "text", "role": "dimension"},
            },
        }
    }
}


def test_summary_carries_counts_and_identifiers():
    out = _render_dataset_summary(_conn(), 98, _CONTEXT)

    assert "Connection ID: 98" in out
    assert "csv_98" in out
    assert "15,000 rows" in out
    assert "3 columns" in out
    # The one-line table description is routing-useful and already shown to the
    # user in the docs message, so it stays.
    assert "Employee HR and performance dataset." in out


def test_summary_withholds_every_column_name_and_meaning():
    out = _render_dataset_summary(_conn(), 98, _CONTEXT)

    for leaked in (
        "satisfaction_level",
        "unnamed_11",
        "salary",
        "Satisfaction Level",
        "Employee-reported satisfaction.",
    ):
        assert leaked not in out, f"{leaked!r} must not reach the orchestrator"


def test_summary_reads_camelcase_row_count():
    """load_enriched_context returns the stored camelCase key. Reading only
    `row_count` silently dropped the row count — the single hard number the
    orchestrator had — leaving it with no quantitative fact at all."""
    assert "15,000 rows" in _render_dataset_summary(_conn(), 98, _CONTEXT)
    snake = {"tables": {"t": {"row_count": 42, "columns": {"a": {}}}}}
    assert "42 rows" in _render_dataset_summary(_conn(), 1, snake)


def test_summary_survives_a_context_with_no_stats():
    out = _render_dataset_summary(_conn(), 7, {"tables": {"t": {}}})
    assert "Connection ID: 7" in out
    assert "table t" in out


def test_summary_tells_the_model_to_query_instead_of_describing():
    out = _render_dataset_summary(_conn(), 98, _CONTEXT)
    assert "data_agent" in out
    assert "Schema metadata only" in out
