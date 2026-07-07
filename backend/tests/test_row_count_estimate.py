"""_get_row_count uses the engine's cached estimate and falls back to COUNT(*).

Fake cursor records the SQL issued, so no real database is needed.
"""
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector

_EXACT = 9999  # value the COUNT(*) fallback returns


class _FakeCursor:
    """Returns `estimate` for the catalog query (reltuples / table_rows) and
    `_EXACT` for a COUNT(*) fallback. `estimate=None` simulates no cached stat."""

    def __init__(self, estimate):
        self.estimate = estimate
        self.executed = []
        self._last = None

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if "reltuples" in sql or "table_rows" in sql:
            self._last = {"count": self.estimate} if self.estimate is not None else None
        elif "COUNT(*)" in sql:
            self._last = {"count": _EXACT}

    def fetchone(self):
        return self._last


def _pg():
    return PostgresConnector("h", 5432, "db", "u", "p")


def _my():
    return MySQLConnector("h", 3306, "db", "u", "p")


def _issued_count_star(cur):
    return any("COUNT(*)" in q for q in cur.executed)


# ── Postgres ───────────────────────────────────────────────────────────────

def test_postgres_uses_estimate_no_scan():
    cur = _FakeCursor(estimate=5000)
    assert _pg()._get_row_count(cur, "public", "orders") == 5000
    assert not _issued_count_star(cur)  # never scanned


def test_postgres_falls_back_when_estimate_zero():
    cur = _FakeCursor(estimate=0)
    assert _pg()._get_row_count(cur, "public", "orders") == _EXACT
    assert _issued_count_star(cur)


def test_postgres_falls_back_when_estimate_missing():
    cur = _FakeCursor(estimate=None)
    assert _pg()._get_row_count(cur, "public", "orders") == _EXACT
    assert _issued_count_star(cur)


# ── MySQL ──────────────────────────────────────────────────────────────────

def test_mysql_uses_estimate_no_scan():
    cur = _FakeCursor(estimate=42)
    assert _my()._get_row_count(cur, "db", "orders") == 42
    assert not _issued_count_star(cur)


def test_mysql_falls_back_when_estimate_zero():
    cur = _FakeCursor(estimate=0)
    assert _my()._get_row_count(cur, "db", "orders") == _EXACT
    assert _issued_count_star(cur)


# ── Base default (unchanged exact behaviour for non-overriding connectors) ──

def test_base_default_is_exact_count():
    cur = _FakeCursor(estimate=123)  # estimate ignored by base impl
    # Call the base method directly to bypass the Postgres override.
    assert BaseConnector._get_row_count(_pg(), cur, "public", "orders") == _EXACT
    assert _issued_count_star(cur)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ok")
