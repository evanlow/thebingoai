from __future__ import annotations

import functools

import sqlglot
import sqlglot.expressions as exp


class UntranspilableSQLError(ValueError):
    """Raised when BigQuery SQL cannot be safely transpiled to DuckDB.

    Carries the offending SQL and a human reason so the Phase 3 migration can
    queue the widget for manual review instead of persisting broken DuckDB SQL.
    """

    def __init__(self, sql: str, reason: str) -> None:
        self.sql = sql
        self.reason = reason
        super().__init__(f"Cannot transpile BigQuery SQL to DuckDB: {reason}")


@functools.lru_cache(maxsize=1)
def _duckdb_function_names() -> frozenset[str]:
    """Lower-cased names of every function DuckDB knows about (cached).

    Used to detect BigQuery functions that sqlglot leaves unmapped — if such a
    function isn't in DuckDB's catalog, running the transpiled SQL would fail,
    so we raise instead of emitting it silently.
    """
    import duckdb

    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT DISTINCT lower(function_name) FROM duckdb_functions()"
        ).fetchall()
        return frozenset(r[0] for r in rows if r[0])
    finally:
        con.close()


def _unknown_duckdb_functions(ast: exp.Expression) -> set[str]:
    """Return function names in *ast* that DuckDB has no definition for.

    Only `exp.Anonymous` nodes are checked — sqlglot renders functions it knows
    how to map as typed nodes, so anything left Anonymous is a function name it
    passed through verbatim. If DuckDB doesn't have that name, it's a gap.
    """
    catalog = _duckdb_function_names()
    unknown: set[str] = set()
    for node in ast.find_all(exp.Anonymous):
        name = (node.name or "").lower()
        if name and name not in catalog:
            unknown.add(name)
    return unknown


_VALID_DIALECTS = frozenset({"bigquery", "duckdb", "postgres", "mysql", "sqlite"})


def transpile_to_engine(sql: str, *, source: str, target: str = "duckdb") -> str:
    """Transpile a single SQL statement from one dialect to another, or raise.

    Steps (each failure raises `UntranspilableSQLError` with a reason):
      1. Parse `sql` under the `source` dialect.
      2. Render in the `target` dialect.
      3. Re-parse the output under `target` — catches dialect-specific syntax
         the generator emitted but the target rejects.
      4. When `target == "duckdb"`: reject output containing functions absent
         from DuckDB's catalog (e.g. `APPROX_QUANTILES` from BigQuery,
         `pg_typeof` from postgres) since they'd 500 the read path at runtime.

    Used by the plane-redirect read paths (widget + chat) so SQL written
    against the source DB (postgres / mysql / bigquery) runs over Parquet via
    DuckDB. `target` defaults to ``"duckdb"`` — the only non-source dialect
    Bingo serves Parquet through today.
    """
    src = (source or "").lower()
    tgt = (target or "").lower()
    if src not in _VALID_DIALECTS:
        raise UntranspilableSQLError(sql, f"unknown source dialect {source!r}")
    if tgt not in _VALID_DIALECTS:
        raise UntranspilableSQLError(sql, f"unknown target dialect {target!r}")

    # Same-dialect short-circuit: parse-validate but skip the round-trip so we
    # don't spuriously rewrite hand-tuned SQL the user already wrote correctly.
    if src == tgt:
        try:
            sqlglot.parse_one(sql, read=src, error_level=sqlglot.ErrorLevel.RAISE)
        except Exception as e:  # noqa: BLE001
            raise UntranspilableSQLError(sql, f"{src} parse failed: {e}") from e
        return sql

    try:
        ast = sqlglot.parse_one(sql, read=src, error_level=sqlglot.ErrorLevel.RAISE)
    except UntranspilableSQLError:
        raise
    except Exception as e:  # noqa: BLE001
        raise UntranspilableSQLError(sql, f"{src} parse failed: {e}") from e

    try:
        out = ast.sql(dialect=tgt)
    except Exception as e:  # noqa: BLE001
        raise UntranspilableSQLError(sql, f"{tgt} generation failed: {e}") from e

    try:
        out_ast = sqlglot.parse_one(out, read=tgt, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception as e:  # noqa: BLE001
        raise UntranspilableSQLError(
            sql, f"transpiled output is not valid {tgt}: {e}",
        ) from e

    if tgt == "duckdb":
        unknown = _unknown_duckdb_functions(out_ast)
        if unknown:
            raise UntranspilableSQLError(
                sql, f"function(s) unsupported by DuckDB: {', '.join(sorted(unknown))}",
            )

    return out


def transpile_bq_to_duckdb(sql: str) -> str:
    """Backwards-compatible shim — defer to `transpile_to_engine`.

    Kept so existing call sites (Phase 3 stored-SQL migration + its tests)
    don't need to change. New code should call `transpile_to_engine` directly.
    """
    return transpile_to_engine(sql, source="bigquery", target="duckdb")


def extract_table_refs(sql: str) -> list[str]:
    """Return list of *physical* table names referenced in *sql* (lower-cased,
    deduplicated, sorted). Returns [] on parse failure.

    CTE names are excluded. sqlglot parses `FROM my_cte` as `exp.Table` exactly
    like `FROM my_real_table` — the node type says "name in FROM position", not
    "table on disk". Callers use this list to resolve storage (register a DuckDB
    view over a Parquet glob, check `table_exists`, build lineage), and a CTE has
    no storage: `WITH bands AS (...) SELECT ... FROM bands` used to yield
    `["bands", "csv_104"]`, so the reader mounted `gs://.../bands/dt=*/*.parquet`,
    got `IO Error: No files found`, and the whole widget fell back to the source DB.

    Excluding is right even when a CTE shadows a real table of the same name —
    inside that query the CTE is what the reference resolves to, so mounting the
    physical table would silently serve different data.

    Exclusion is resolved **per scope**, not against one statement-wide set of CTE
    names, because a bare-name match is not proof that a reference is the CTE:
    `WITH orders AS (SELECT * FROM orders) SELECT * FROM orders` has a physical
    `orders` inside the CTE body (a non-recursive CTE cannot reference itself), and
    `WITH orders AS (...) ... FROM public.orders` is qualified. Both used to return
    `[]`. That matters beyond serving: the org-governance plugin enforces per-table
    ACLs by iterating this list, so an empty list means no authorization check runs
    at all.

    When in doubt this over-reports. Naming a table that isn't on the plane only
    costs a failed view registration and a fallback to the source DB; missing one
    has no equivalent backstop.
    """
    try:
        parsed = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception:
        return []

    physical: set[str] = set()   # names a scope resolved to a real table
    cte_bound: set[str] = set()  # names a scope resolved to a CTE / derived table

    # `scope.sources` maps each name visible in a scope to an `exp.Table` when it
    # is a physical reference, or to a nested `Scope` when it is a CTE or derived
    # table — exactly the distinction the bare-name match could not make.
    try:
        from sqlglot.optimizer.scope import traverse_scope

        for scope in traverse_scope(parsed):
            for name, source in scope.sources.items():
                if isinstance(source, exp.Table):
                    if source.name:
                        physical.add(source.name.lower())
                elif name:
                    cte_bound.add(name.lower())
    except Exception:
        # Leaves cte_bound empty, so the backfill below reports every name — the
        # safe direction (see docstring) rather than a silent under-report.
        pass

    # Nodes the scope walk doesn't reach (an INSERT target, DDL) are still real
    # tables. Only a name bound to a CTE somewhere is suppressed here; a name the
    # walk already resolved to a physical table stays, so a CTE in one scope
    # cannot hide a real table of the same name in another.
    for node in parsed.find_all(exp.Table):
        if node.name and node.name.lower() not in cte_bound:
            physical.add(node.name.lower())

    return sorted(physical)


def qualifier_allowlist(connection) -> set[str] | None:
    """Schemas whose qualifier may be dropped when rewriting *connection*'s
    tables to bare-named plane views.

    A ref qualified with a schema outside this set is a different table that
    merely shares the bare name (e.g. ``archive.orders`` vs the piped
    ``public.orders``) and must not be rewritten. ``None`` = drop any
    qualifier — BigQuery-style sources, where ``proj.ds.x`` qualifiers always
    refer to the connection's own tables.
    """
    db_type = (getattr(connection, "db_type", "") or "").lower()
    if db_type in ("postgres", "postgresql"):
        return {"public"}
    if db_type == "sqlite":
        return {"main"}
    if db_type in ("mssql", "sqlserver"):
        return {"dbo"}
    if db_type == "mysql":
        database = (getattr(connection, "database", "") or "").lower()
        return {database} if database else None
    return None


def rewrite_table_refs(
    sql: str, mapping: dict[str, str], allowed_schemas: set[str] | None = None
) -> tuple[str, bool]:
    """Rewrite table references in *sql* using *mapping* (old_name → new_name, case-insensitive).
    Returns (rewritten_sql, success). success=False if sql could not be parsed.

    *allowed_schemas*: schema qualifiers that may be dropped in the rewrite
    (see `qualifier_allowlist`). None drops any qualifier."""
    try:
        parsed = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception:
        return (sql, False)

    normalized_mapping = {k.lower(): v for k, v in mapping.items()}

    def _rewriter(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Table) and node.name and node.name.lower() in normalized_mapping:
            if node.db and allowed_schemas is not None and node.db.lower() not in allowed_schemas:
                return node  # other-schema table sharing the bare name — not ours
            new_name = normalized_mapping[node.name.lower()]
            new_node = node.copy()
            new_node.this.args["this"] = new_name  # mutate the Identifier's raw string
            new_node.set("db", None)       # plane views are bare-named — drop schema
            new_node.set("catalog", None)  # …and catalog, so public.x / proj.ds.x resolve
            return new_node
        return node

    try:
        rewritten = parsed.transform(_rewriter)
        return (rewritten.sql(), True)
    except Exception:
        return (sql, False)


def can_parse(sql: str) -> bool:
    """Return True if sqlglot can parse *sql* without errors."""
    try:
        sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
        return True
    except Exception:
        return False
