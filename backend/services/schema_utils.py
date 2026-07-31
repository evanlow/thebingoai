"""Shared schema utilities for SQL fix suggestions and schema summaries."""
import logging

logger = logging.getLogger(__name__)


def normalize_sql_for(sql: str, dialect: str) -> str:
    """Rewrite widget SQL for *dialect*: quote reserved-word identifiers, fix quoting.

    The agent writes ANSI double-quoted identifiers whatever the target is, so
    `c."role"` reaches BigQuery as a *string literal* (not a column), and a column
    literally named `left`/`order`/`end` used unquoted is a syntax error in every
    dialect. One parse → re-emit pass fixes both.

    Returns *sql* byte-identical when nothing needs changing, and on any failure —
    never block a query that would have worked.
    """
    if not sql or not dialect:
        return sql
    try:
        import sqlglot
        from sqlglot import exp

        # ponytail: backticks are the tell for BigQuery-flavoured SQL, where
        # "..." is a string; everything else is ANSI, where it is an identifier.
        # Reading with the wrong one silently swaps the two. Upgrade path if this
        # misfires: pass the authoring dialect down from the agent instead.
        read = "bigquery" if "`" in sql else "postgres"
        target = sqlglot.Dialect.get_or_raise(dialect)
        tree = sqlglot.parse_one(sql, read=read)

        keywords = target.tokenizer_class.KEYWORDS
        changed = False
        for node in tree.find_all(exp.Identifier):
            # Only lowercase names: quoting a mixed-case identifier changes what
            # it resolves to under Postgres' unquoted case folding.
            if node.quoted or node.name != node.name.lower():
                continue
            if node.name.upper() in keywords:
                node.set("quoted", True)
                changed = True

        read_quote = "`" if read == "bigquery" else '"'
        if not changed and target.tokenizer_class.IDENTIFIERS[0] == read_quote:
            return sql  # same quoting flavour, nothing to fix — don't re-emit
        return tree.sql(dialect=dialect)
    except Exception as exc:
        logger.debug("SQL normalization for %s skipped: %s", dialect, exc)
        return sql


def extract_table_names(sql: str) -> set:
    """Extract table names referenced after FROM/JOIN keywords.

    Delegates to backend.agents.sql_validation.extract_table_refs (the canonical
    parser, which also handles aliases). Returns the lowercase name set only.
    """
    from backend.agents.sql_validation import extract_table_refs
    table_matches, _ = extract_table_refs(sql)
    return {m.lower() for m in table_matches}


def build_schema_summary(schema_json: dict, referenced_tables: set) -> str:
    """Build a concise text summary of schema tables relevant to the SQL query."""
    lines = []

    # Support two schema formats:
    # 1. Flat: {"tables": [...]}
    # 2. Nested: {"schemas": {"public": {"tables": {"name": {"columns": [...]}}}}}
    flat_tables = schema_json.get('tables', [])
    if flat_tables:
        tables_list = flat_tables
    else:
        tables_list = []
        for schema_name, schema_body in schema_json.get('schemas', {}).items():
            for table_name, table_body in schema_body.get('tables', {}).items():
                cols = table_body.get('columns', [])
                if isinstance(cols, list):
                    columns = [{'name': c.get('name', c) if isinstance(c, dict) else c,
                                'data_type': c.get('type', c.get('data_type', '')) if isinstance(c, dict) else ''} for c in cols]
                else:
                    columns = [{'name': k, 'data_type': v.get('type', v.get('data_type', '')) if isinstance(v, dict) else ''}
                               for k, v in cols.items()]
                tables_list.append({
                    'name': table_name,
                    'row_count': table_body.get('row_count', '?'),
                    'columns': columns,
                })

    all_table_names = [t.get('name', '') for t in tables_list]
    lines.append(f"Available tables: {', '.join(all_table_names)}")
    lines.append("")

    filtered = [t for t in tables_list if t.get('name', '').lower() in referenced_tables]
    if not filtered:
        filtered = tables_list[:10]

    for table in filtered:
        name = table.get('name', '')
        row_count = table.get('row_count', '?')
        columns = table.get('columns', [])
        col_summary = ', '.join(
            f"{c.get('name')} ({c.get('data_type', 'unknown')})" for c in columns
        )
        lines.append(f"Table: {name} ({row_count} rows)")
        lines.append(f"  Columns: {col_summary}")

    relationships = schema_json.get('relationships', [])
    if relationships and isinstance(relationships, list):
        rel_parts = []
        for r in relationships:
            # Support both formats:
            # Format A: {from: 'table.column', to: 'table.column'}
            # Format B: {from_table: 't', from_column: 'c', to_table: 't', to_column: 'c'}
            if 'from' in r and '.' in str(r.get('from', '')):
                from_parts = str(r['from']).split('.', 1)
                to_parts = str(r.get('to', '')).split('.', 1)
                from_table = from_parts[0]
                from_col = from_parts[1] if len(from_parts) > 1 else ''
                to_table = to_parts[0]
                to_col = to_parts[1] if len(to_parts) > 1 else ''
            else:
                from_table = r.get('from_table', '')
                from_col = r.get('from_column', '')
                to_table = r.get('to_table', '')
                to_col = r.get('to_column', '')
            if from_table.lower() in referenced_tables or to_table.lower() in referenced_tables:
                rel_parts.append(f"{from_table}.{from_col} -> {to_table}.{to_col}")
        if rel_parts:
            lines.append("Relationships: " + '; '.join(rel_parts))

    return '\n'.join(lines)
