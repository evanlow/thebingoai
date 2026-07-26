"""The dashboard runtime suffix carries semantic-layer meaning with the schema."""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.agents.dashboard_agent.prompts import build_dashboard_runtime_suffix

_CTX = {
    "tables": {
        "sales_q4": {
            "columns": {
                "chn": {"type": "text", "role": "dimension"},
                "rev_amt": {"type": "numeric", "role": "measure"},
            },
        }
    }
}


def _suffix(ctx):
    conn = SimpleNamespace(id=7, name="sales_q4.csv", db_type="dataset", database="d")
    with patch("backend.database.session.SessionLocal", return_value=MagicMock()), \
         patch("backend.services.semantic_layer.load_enriched_context", return_value=ctx):
        return build_dashboard_runtime_suffix(
            available_connections=[7], connection_metadata=[conn],
        )


def test_suffix_without_glossary_lists_bare_column_names():
    assert "sales_q4: dimensions=[chn] measures=[rev_amt]" in _suffix(copy.deepcopy(_CTX))


def test_suffix_carries_display_name_and_description():
    ctx = copy.deepcopy(_CTX)
    table = ctx["tables"]["sales_q4"]
    table["description"] = "Line-level order revenue by channel"
    table["columns"]["chn"]["displayName"] = "Channel"
    table["columns"]["chn"]["description"] = "acquisition source"
    table["columns"]["rev_amt"]["description"] = "order revenue in MYR, excludes tax"

    out = _suffix(ctx)
    assert "sales_q4 — Line-level order revenue by channel:" in out
    assert "dimensions=[chn (Channel) — acquisition source]" in out
    assert "measures=[rev_amt — order revenue in MYR, excludes tax]" in out


def test_columns_are_separated_by_semicolons_so_commas_in_descriptions_are_unambiguous():
    """A description containing a comma must not read as an extra column."""
    ctx = copy.deepcopy(_CTX)
    cols = ctx["tables"]["sales_q4"]["columns"]
    cols["chn"]["description"] = "acquisition source, one of FB/GG/ORG"
    cols["ctry"] = {"type": "text", "role": "dimension"}

    out = _suffix(ctx)
    assert "dimensions=[chn — acquisition source, one of FB/GG/ORG; ctry]" in out
