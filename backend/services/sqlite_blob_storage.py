"""Storage routing for SQLite connector blobs.

New uploads live on the owner's DataPlane as raw objects, keyed on
``connection.dataset_table_name`` with a ``dp:`` marker prefix
(``dp:sqlite_blobs/<connection.uuid>.sqlite``). Keys without the marker
(and not absolute filesystem paths) are legacy DO Spaces keys — kept
readable for un-migrated rows and the FacebookAds/Notion plugin blobs.
"""
from __future__ import annotations

from typing import Optional

DP_PREFIX = "dp:"


def is_data_plane_key(key: Optional[str]) -> bool:
    return bool(key) and key.startswith(DP_PREFIX)


def rel_path_for(connection) -> str:
    return f"sqlite_blobs/{connection.uuid}.sqlite"


def _plane_and_scope(connection, db=None):
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane

    scope = OwnerScope.from_connection(connection)
    return get_default_plane(scope, db), scope


def save_blob(connection, data: bytes, db=None) -> str:
    """Write *data* to the connection's DataPlane; return the dp: key.

    The caller persists the returned key on ``connection.dataset_table_name``.
    """
    plane, scope = _plane_and_scope(connection, db)
    rel = rel_path_for(connection)
    plane.put_raw_object(scope, rel, data, content_type="application/x-sqlite3")
    return DP_PREFIX + rel


def load_blob(connection, db=None) -> Optional[bytes]:
    """Read the connection's blob bytes; None when key unset or object absent."""
    key = connection.dataset_table_name
    if not key:
        return None
    if is_data_plane_key(key):
        plane, scope = _plane_and_scope(connection, db)
        return plane.get_raw_object(scope, key[len(DP_PREFIX):])
    from backend.services import object_storage

    return object_storage.download_bytes(key)


def delete_blob(connection, db=None) -> None:
    key = connection.dataset_table_name
    if not key:
        return
    if is_data_plane_key(key):
        plane, scope = _plane_and_scope(connection, db)
        plane.delete_raw_object(scope, key[len(DP_PREFIX):])
        return
    from backend.services import object_storage

    object_storage.delete_object(key)


def blob_exists(connection, db=None) -> bool:
    key = connection.dataset_table_name
    if not key:
        return False
    if is_data_plane_key(key):
        from backend.data_plane.errors import NoPlaneProvisionedError

        try:
            plane, scope = _plane_and_scope(connection, db)
        except NoPlaneProvisionedError:
            return False
        return plane.raw_object_exists(scope, key[len(DP_PREFIX):])
    from backend.services import object_storage

    return object_storage.object_exists(key)
