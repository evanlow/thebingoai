"""Tests for sqlite_blob_storage routing (dp: → DataPlane, else → legacy DO Spaces)."""
from unittest.mock import MagicMock, patch

import pytest

from backend.data_plane.errors import NoPlaneProvisionedError
from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
from backend.data_plane.scope import OwnerScope
from backend.services import sqlite_blob_storage


def _connection(uuid="conn-uuid-1", dataset_table_name=None):
    conn = MagicMock()
    conn.uuid = uuid
    conn.dataset_table_name = dataset_table_name
    conn.owner_scope_kind = "user"
    conn.owner_scope_id = "user-1"
    conn.org_id = None
    conn.user_id = "user-1"
    return conn


def test_is_data_plane_key():
    assert sqlite_blob_storage.is_data_plane_key("dp:sqlite_blobs/x.sqlite") is True
    assert sqlite_blob_storage.is_data_plane_key("bingo/dev/u/sqlite/x.sqlite") is False
    assert sqlite_blob_storage.is_data_plane_key(None) is False
    assert sqlite_blob_storage.is_data_plane_key("") is False


def test_save_and_load_round_trip(tmp_path):
    plane = LocalFilesystemDataPlane(root_path=str(tmp_path))
    conn = _connection()
    with patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        key = sqlite_blob_storage.save_blob(conn, b"sqlite-bytes")
        assert key == "dp:sqlite_blobs/conn-uuid-1.sqlite"
        conn.dataset_table_name = key
        assert sqlite_blob_storage.load_blob(conn) == b"sqlite-bytes"


def test_delete_blob_dp_key_removes_object(tmp_path):
    plane = LocalFilesystemDataPlane(root_path=str(tmp_path))
    conn = _connection()
    with patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        conn.dataset_table_name = sqlite_blob_storage.save_blob(conn, b"sqlite-bytes")
        sqlite_blob_storage.delete_blob(conn)
        assert sqlite_blob_storage.load_blob(conn) is None


def test_blob_exists_dp_key(tmp_path):
    plane = LocalFilesystemDataPlane(root_path=str(tmp_path))
    conn = _connection(dataset_table_name="dp:sqlite_blobs/conn-uuid-1.sqlite")
    with patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        assert sqlite_blob_storage.blob_exists(conn) is False
        conn.dataset_table_name = sqlite_blob_storage.save_blob(conn, b"sqlite-bytes")
        assert sqlite_blob_storage.blob_exists(conn) is True


def test_blob_exists_no_plane_returns_false():
    conn = _connection(dataset_table_name="dp:sqlite_blobs/conn-uuid-1.sqlite")
    scope = OwnerScope("user", "user-1")
    with patch(
        "backend.services.data_plane_service.get_default_plane",
        side_effect=NoPlaneProvisionedError(scope),
    ):
        assert sqlite_blob_storage.blob_exists(conn) is False


def test_load_blob_none_key_returns_none():
    assert sqlite_blob_storage.load_blob(_connection(dataset_table_name=None)) is None


def test_legacy_key_routes_to_object_storage():
    conn = _connection(dataset_table_name="bingo/dev/user-1/sqlite/conn-uuid-1.sqlite")
    with patch("backend.services.object_storage.download_bytes", return_value=b"legacy") as dl, \
         patch("backend.services.object_storage.delete_object") as do, \
         patch("backend.services.object_storage.object_exists", return_value=True) as oe:
        assert sqlite_blob_storage.load_blob(conn) == b"legacy"
        sqlite_blob_storage.delete_blob(conn)
        assert sqlite_blob_storage.blob_exists(conn) is True

    dl.assert_called_once_with("bingo/dev/user-1/sqlite/conn-uuid-1.sqlite")
    do.assert_called_once_with("bingo/dev/user-1/sqlite/conn-uuid-1.sqlite")
    oe.assert_called_once_with("bingo/dev/user-1/sqlite/conn-uuid-1.sqlite")


def test_save_blob_propagates_no_plane_error():
    conn = _connection()
    scope = OwnerScope("user", "user-1")
    with patch(
        "backend.services.data_plane_service.get_default_plane",
        side_effect=NoPlaneProvisionedError(scope),
    ):
        with pytest.raises(NoPlaneProvisionedError):
            sqlite_blob_storage.save_blob(conn, b"sqlite-bytes")
