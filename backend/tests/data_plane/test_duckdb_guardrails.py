"""DuckDB memory guardrails: every connect site caps memory and enables spill.

DuckDB's default memory_limit is ~80% of system RAM per connection; serving
opens one connection per request, so concurrent reads could OOM the container
without these settings.
"""
from __future__ import annotations

import duckdb
import pytest

from backend.config import settings
from backend.data_plane.duckdb_exec import apply_memory_guardrails


def _current_setting(conn, name: str) -> str:
    return conn.execute(f"SELECT current_setting('{name}')").fetchone()[0]


def test_guardrails_apply_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "duckdb_memory_limit", "256MB")
    monkeypatch.setattr(settings, "duckdb_temp_directory", str(tmp_path / "spill"))

    conn = duckdb.connect()
    try:
        apply_memory_guardrails(conn)
        assert _current_setting(conn, "memory_limit") in ("256.0 MiB", "244.1 MiB", "256MB")
        assert _current_setting(conn, "temp_directory") == str(tmp_path / "spill")
        assert (tmp_path / "spill").is_dir()  # created for the spill path
    finally:
        conn.close()


def test_guardrails_failure_never_raises(monkeypatch):
    monkeypatch.setattr(settings, "duckdb_memory_limit", "not-a-size")
    conn = duckdb.connect()
    try:
        apply_memory_guardrails(conn)  # logs a warning, must not raise
    finally:
        conn.close()


def test_local_filesystem_plane_connection_has_guardrails(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "duckdb_memory_limit", "256MB")
    monkeypatch.setattr(settings, "duckdb_temp_directory", str(tmp_path / "spill"))

    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane

    plane = LocalFilesystemDataPlane(str(tmp_path / "root"))
    try:
        conn = plane._get_conn()
        assert _current_setting(conn, "temp_directory") == str(tmp_path / "spill")
    finally:
        plane.close()


def test_gcs_reader_connection_has_guardrails(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "duckdb_memory_limit", "256MB")
    monkeypatch.setattr(settings, "duckdb_temp_directory", str(tmp_path / "spill"))

    from backend.data_plane.gcs_duckdb import GCSDuckDBReader

    reader = GCSDuckDBReader("bucket", "key-id", "secret")
    try:
        conn = reader._get_conn()
        assert _current_setting(conn, "temp_directory") == str(tmp_path / "spill")
    finally:
        reader.close()
