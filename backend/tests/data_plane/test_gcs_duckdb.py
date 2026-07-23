"""Tests for the DuckDB-over-GCS reader (Phase 2, 2a).

The live gs:// read needs real GCP + HMAC; here the glob is monkeypatched to a
local Parquet file so view registration, binding, and the row cap are exercised
end-to-end without network.
"""
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import backend.data_plane.bigquery_gcs as bqmod
from backend.data_plane.bigquery_gcs import gcs_parquet_glob
from backend.data_plane.gcs_duckdb import GCSDuckDBReader, _secret_sql, _view_sql
from backend.data_plane.scope import OwnerScope


def test_glob_scheme_matches_lake_layout():
    g = gcs_parquet_glob("bkt", OwnerScope("org", "o1"), "csv_1")
    assert g == "gs://bkt/data_plane/org/o1/csv_1/dt=*/*.parquet"


def test_secret_sql_is_gcs_hmac():
    s = _secret_sql("GOOGKEY", "sec")
    assert "TYPE GCS" in s and "GOOGKEY" in s and "sec" in s


def test_secret_sql_rejects_quotes():
    with pytest.raises(ValueError):
        _secret_sql("a'b", "s")


def test_view_sql_sanitizes_and_reads_parquet():
    v = _view_sql("my-tbl", "gs://x/y")
    assert "my_tbl" in v
    assert "read_parquet('gs://x/y'" in v
    assert "hive_partitioning=true" in v


def test_get_conn_applies_http_caps(monkeypatch):
    """_get_conn must bound GCS network I/O (PR #148) so a stalled read fails
    fast instead of hanging past the frontend's 60s cap. Spy on the connection's
    execute() to confirm the three SET pragmas are issued with the configured
    values, while delegating to a real DuckDB conn so httpfs still loads."""
    import duckdb

    from backend.config import settings

    real_connect = duckdb.connect
    recorded: list[str] = []

    class _RecordingConn:
        def __init__(self, real):
            self._real = real

        def execute(self, sql, *args, **kwargs):
            recorded.append(sql)
            return self._real.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    monkeypatch.setattr(duckdb, "connect", lambda *a, **k: _RecordingConn(real_connect()))

    reader = GCSDuckDBReader("bkt", "GOOGKEY", "secret")
    try:
        reader._get_conn()
    finally:
        reader.close()

    assert f"SET http_timeout = {settings.duckdb_http_timeout_ms}" in recorded
    assert f"SET http_retries = {settings.duckdb_http_retries}" in recorded
    assert "SET http_keep_alive = true" in recorded


def _write(path):
    pq.write_table(
        pa.table({"region": ["EMEA", "APAC"], "amount": pa.array([10, 7], type=pa.int64())}),
        path,
    )


def test_reader_query_over_local_parquet(tmp_path, monkeypatch):
    f = tmp_path / "data.parquet"
    _write(f)
    monkeypatch.setattr(bqmod, "gcs_parquet_glob", lambda bucket, scope, table: str(f))

    reader = GCSDuckDBReader("bkt", "GOOGKEY", "secret")
    try:
        res = reader.query(OwnerScope("org", "o1"), "SELECT region, amount FROM csv_1 ORDER BY amount")
        assert res.columns == ["region", "amount"]
        assert [r[0] for r in res.rows] == ["APAC", "EMEA"]
        assert res.truncated is False
    finally:
        reader.close()


def test_reader_named_param_binding(tmp_path, monkeypatch):
    f = tmp_path / "d.parquet"
    _write(f)
    monkeypatch.setattr(bqmod, "gcs_parquet_glob", lambda *a: str(f))

    reader = GCSDuckDBReader("bkt", "K", "S")
    try:
        res = reader.query(
            OwnerScope("org", "o1"),
            "SELECT amount FROM csv_1 WHERE region = $_f0",
            {"_f0": "EMEA"},
        )
        assert [r[0] for r in res.rows] == [10]
    finally:
        reader.close()


def test_register_views_dedups_per_glob(tmp_path, monkeypatch):
    # A reader reused across widgets must register each table's view once, not
    # once per query — the win behind sharing one reader for a whole dashboard.
    f = tmp_path / "d.parquet"
    _write(f)
    monkeypatch.setattr(bqmod, "gcs_parquet_glob", lambda *a: str(f))

    reader = GCSDuckDBReader("bkt", "K", "S")
    try:
        scope = OwnerScope("org", "o1")
        reader.query(scope, "SELECT region FROM csv_1")
        reader.query(scope, "SELECT amount FROM csv_1 ORDER BY amount")
        assert reader._registered_globs == {str(f)}  # registered once across both queries
    finally:
        reader.close()


def test_close_clears_registered_globs(tmp_path, monkeypatch):
    # close() must reset the per-connection registry so a reused reader object
    # re-registers after its connection is dropped.
    f = tmp_path / "d.parquet"
    _write(f)
    monkeypatch.setattr(bqmod, "gcs_parquet_glob", lambda *a: str(f))

    reader = GCSDuckDBReader("bkt", "K", "S")
    reader.query(OwnerScope("org", "o1"), "SELECT region FROM csv_1")
    assert reader._registered_globs
    reader.close()
    assert reader._registered_globs == set()
