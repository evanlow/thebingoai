"""Upload must queue profiling+migration even when schema storage fails.

Schema generation is best-effort (caught and logged), so gating the chain on
`schema_json_path` left a 201'd connection holding only a raw blob, with no
profiling, no migration, and no recovery path. `profile_connection`
rediscovers the schema itself, so the gate was redundant as well as harmful.

Calls the endpoint coroutine directly — no TestClient, so no app fixture.
"""
import asyncio
import sqlite3
import tempfile
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sqlite_bytes():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.execute('CREATE TABLE orders ("order-id" TEXT PRIMARY KEY, "Order Total" REAL)')
        conn.execute('INSERT INTO orders VALUES (?, ?)', ("a1", 9.5))
        conn.commit()
        conn.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


class _UploadFile:
    def __init__(self, filename, data):
        self.filename = filename
        self._data = data

    async def read(self):
        return self._data


async def _run_upload(sqlite_bytes, *, schema_save_raises):
    from backend.api import sqlite_upload

    db = MagicMock()
    user = MagicMock(id="u1")
    save_schema = MagicMock(side_effect=RuntimeError("storage down")) if schema_save_raises \
        else MagicMock(return_value="schemas/c1.json")

    with patch.object(sqlite_upload, "save_schema_file", save_schema), \
         patch("backend.services.sqlite_blob_storage.save_blob", return_value="orgs/u1/db.sqlite"), \
         patch("backend.tasks.migration_tasks.enqueue_profile_then_migrate") as enqueue, \
         patch.object(sqlite_upload.settings, "enable_governance", False):
        await sqlite_upload.upload_sqlite(
            file=_UploadFile("orders.sqlite", sqlite_bytes),
            name="orders",
            current_user=user,
            db=db,
        )
    return enqueue


def test_enqueues_when_schema_saved(sqlite_bytes):
    enqueue = asyncio.run(_run_upload(sqlite_bytes, schema_save_raises=False))
    enqueue.assert_called_once()


def test_enqueues_even_when_schema_save_fails(sqlite_bytes):
    enqueue = asyncio.run(_run_upload(sqlite_bytes, schema_save_raises=True))
    enqueue.assert_called_once()
