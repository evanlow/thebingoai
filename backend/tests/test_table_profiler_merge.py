"""Checks for the single-scan merge + per-type fallback in table_profiler.

A fake connector records the SQL issued and returns canned rows, so no real
database is needed. Run under the backend test env (pytest, or
`python3 test_table_profiler_merge.py`) where the app deps are installed.
"""
from backend.services.table_profiler import profile_table


class _Res:
    def __init__(self, rows):
        self.rows = rows


class _FakeConn:
    """Records queries. Returns one combined stats row for the merged scan,
    and grouped rows for top-values. If `fail_combined` is set, the combined
    scan raises and the per-type fallback queries are served instead."""

    def __init__(self, fail_combined=False):
        self.queries = []
        self.fail_combined = fail_combined

    def execute_query(self, sql):
        self.queries.append(sql)
        is_combined = "AVG(" in sql and "COUNT(DISTINCT" in sql
        # Stats scans (no GROUP BY) — combined or per-type.
        if "GROUP BY" not in sql:
            if is_combined:
                if self.fail_combined:
                    raise RuntimeError("boom: bad column in combined scan")
                # order: MIN/MAX/AVG/null(n), MIN/MAX/null(d), DISTINCT/null(t)
                return _Res([[1, 100, 50.0, 0, "2020-01-01", "2020-12-31", 2, 3, 1]])
            if "AVG(" in sql:          # per-type numeric
                return _Res([[1, 100, 50.0, 0]])
            if "MIN(" in sql:         # per-type date
                return _Res([["2020-01-01", "2020-12-31", 2]])
            if "COUNT(DISTINCT" in sql:  # per-type categorical
                return _Res([[3, 1]])
        # Top-values (Query D)
        return _Res([["a", 10], ["b", 5]])

    def close(self):
        pass


_COLUMNS = [
    {"name": "n", "type": "integer"},
    {"name": "d", "type": "date"},
    {"name": "t", "type": "text"},
]


def _profile(fail_combined):
    conn = _FakeConn(fail_combined=fail_combined)
    result = profile_table(
        connector=conn,
        table_name="orders",
        schema_name="public",
        columns=_COLUMNS,
        row_count=123,
        db_type="postgres",
    )
    return conn, result["columns"]


def test_single_combined_scan_exact():
    conn, cols = _profile(fail_combined=False)
    # Exactly one stats scan (the rest are top-values GROUP BY queries).
    stats_scans = [q for q in conn.queries if "GROUP BY" not in q]
    assert len(stats_scans) == 1, stats_scans
    assert cols["n"] == {"type": "numeric", "min": 1, "max": 100, "avg": 50.0, "null_count": 0}
    assert cols["d"]["type"] == "date" and cols["d"]["min"] == "2020-01-01"
    assert cols["t"]["distinct_count"] == 3 and cols["t"]["null_count"] == 1
    assert cols["t"]["top_values"] == ["a", "b"]


def test_fallback_to_per_type_on_combined_failure():
    conn, cols = _profile(fail_combined=True)
    # Combined failed → three per-type stats scans issued instead of one.
    stats_scans = [q for q in conn.queries if "GROUP BY" not in q]
    assert len(stats_scans) == 4, stats_scans  # 1 failed combined + 3 per-type
    # All columns still profiled correctly via the fallback.
    assert cols["n"]["avg"] == 50.0
    assert cols["d"]["max"] == "2020-12-31"
    assert cols["t"]["distinct_count"] == 3


if __name__ == "__main__":
    test_single_combined_scan_exact()
    test_fallback_to_per_type_on_combined_failure()
    print("ok")
