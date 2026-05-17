"""`BigQueryGCSPlane._rewrite_sql` table-name rewrite must be idempotent
for already-backticked references — the dashboard agent now emits
``FROM `insights_daily` `` and the rewrite previously double-wrapped the
backticks, yielding ``Invalid empty identifier`` from BigQuery.
"""
from unittest.mock import patch

import pytest

from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
from backend.data_plane.scope import OwnerScope


@pytest.fixture
def plane():
    p = BigQueryGCSPlane(
        gcp_project="proj",
        gcs_bucket="bkt",
        bq_dataset="ds",
        service_account_json="{}",
    )
    return p


@pytest.fixture
def scope():
    return OwnerScope("org", "abc")


@pytest.fixture
def expected_fqn():
    # _bq_table_name("org/abc", "insights_daily") = "org__abc__insights_daily"
    return "`proj.ds.org__abc__insights_daily`"


def _patched(plane, scope, sql):
    with patch.object(plane, "list_tables", return_value=["insights_daily"]):
        return plane._rewrite_sql(scope, sql)


def test_bare_table_name_rewritten_to_fqn(plane, scope, expected_fqn):
    sql = "SELECT 1 FROM insights_daily WHERE x = 1"
    out = _patched(plane, scope, sql)
    assert out == f"SELECT 1 FROM {expected_fqn} WHERE x = 1"


def test_backticked_table_name_does_not_double_wrap(plane, scope, expected_fqn):
    """LLM emits backticks; rewrite must preserve a single backtick pair."""
    sql = "SELECT 1 FROM `insights_daily` WHERE x = 1"
    out = _patched(plane, scope, sql)
    assert out == f"SELECT 1 FROM {expected_fqn} WHERE x = 1"
    # No adjacent backticks anywhere (would produce empty identifier in BQ).
    assert "``" not in out


def test_already_fqn_is_idempotent(plane, scope, expected_fqn):
    """Re-running rewrite on its own output must not re-wrap the FQN."""
    sql = f"SELECT 1 FROM {expected_fqn} WHERE x = 1"
    out = _patched(plane, scope, sql)
    assert out == sql
    assert "``" not in out
