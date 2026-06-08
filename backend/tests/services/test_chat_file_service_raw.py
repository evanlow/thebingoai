"""Tests for chat_file_service raw-file storage routing (dataset → plane, else → DO)."""
from unittest.mock import MagicMock, patch

from backend.data_plane.scope import OwnerScope


def test_save_raw_file_dataset_goes_to_plane():
    from backend.services import chat_file_service

    plane = MagicMock()
    scope = OwnerScope("user", "user-1")
    with patch("backend.services.data_plane_service.get_default_plane", return_value=plane) as gdp:
        key = chat_file_service.save_raw_file(
            scope, "thread-9", "file-7", "report.csv", b"a,b\n1,2\n", "text/csv",
        )

    assert key == "chat_files/thread-9/file-7.csv"
    gdp.assert_called_once_with(scope)
    plane.put_raw_object.assert_called_once_with(
        scope, "chat_files/thread-9/file-7.csv", b"a,b\n1,2\n", "text/csv",
    )


def test_save_raw_file_image_uses_do(monkeypatch):
    from backend.services import chat_file_service

    scope = OwnerScope("user", "user-1")
    uploaded = {}

    def fake_upload(key, data, content_type):
        uploaded["key"] = key

    monkeypatch.setattr(chat_file_service.settings, "do_spaces_base_path", "bingo/test")
    with patch("backend.services.object_storage.upload_bytes", side_effect=fake_upload):
        key = chat_file_service.save_raw_file(
            scope, "thread-9", "file-7", "pic.png", b"\x89PNG", "image/png",
        )

    assert key == "bingo/test/user-1/raw/file-7.png"
    assert uploaded["key"] == "bingo/test/user-1/raw/file-7.png"


def test_save_raw_file_xlsx_goes_to_plane():
    from backend.services import chat_file_service

    plane = MagicMock()
    scope = OwnerScope("user", "user-1")
    excel_mime = chat_file_service.EXCEL_MIME_TYPE
    with patch("backend.services.data_plane_service.get_default_plane", return_value=plane) as gdp:
        key = chat_file_service.save_raw_file(
            scope, "thread-9", "file-7", "report.xlsx", b"PK\x03\x04xlsx", excel_mime,
        )

    assert key == "chat_files/thread-9/file-7.xlsx"
    gdp.assert_called_once_with(scope)
    plane.put_raw_object.assert_called_once_with(
        scope, "chat_files/thread-9/file-7.xlsx", b"PK\x03\x04xlsx", excel_mime,
    )


def test_save_raw_file_routes_by_extension_not_content_type():
    """A .csv mislabeled with a non-dataset content_type still lands in the plane,
    so save and get_raw_file (which routes by ext) stay consistent."""
    from backend.services import chat_file_service

    plane = MagicMock()
    scope = OwnerScope("user", "user-1")
    with patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        key = chat_file_service.save_raw_file(
            scope, "thread-9", "file-7", "report.csv", b"a,b\n1,2\n", "application/octet-stream",
        )

    assert key == "chat_files/thread-9/file-7.csv"
    plane.put_raw_object.assert_called_once_with(
        scope, "chat_files/thread-9/file-7.csv", b"a,b\n1,2\n", "application/octet-stream",
    )


def test_get_raw_file_missing_thread_id_returns_none():
    """Record exists with a dataset ext but no thread_id → returns None without
    touching the plane."""
    from backend.services import chat_file_service

    plane = MagicMock()
    file_data = {"original_name": "report.csv"}  # no thread_id key
    with patch.object(chat_file_service, "get_file", return_value=file_data), \
         patch("backend.services.data_plane_service.get_default_plane", return_value=plane) as gdp:
        assert chat_file_service.get_raw_file("user-1", "file-7") is None

    gdp.assert_not_called()
    plane.get_raw_object.assert_not_called()


def test_get_raw_file_non_dataset_ext_returns_none():
    """Record exists but original_name isn't .csv/.xlsx → ext guard returns None
    without ever touching the plane."""
    from backend.services import chat_file_service

    plane = MagicMock()
    file_data = {"thread_id": "thread-9", "original_name": "scan.pdf"}
    with patch.object(chat_file_service, "get_file", return_value=file_data), \
         patch("backend.services.data_plane_service.get_default_plane", return_value=plane) as gdp:
        assert chat_file_service.get_raw_file("user-1", "file-7") is None

    gdp.assert_not_called()
    plane.get_raw_object.assert_not_called()


def test_get_raw_file_reads_from_plane():
    from backend.services import chat_file_service

    plane = MagicMock()
    plane.get_raw_object.return_value = b"a,b\n1,2\n"
    file_data = {"thread_id": "thread-9", "original_name": "report.csv"}
    with patch.object(chat_file_service, "get_file", return_value=file_data), \
         patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        result = chat_file_service.get_raw_file("user-1", "file-7")

    assert result == (b"a,b\n1,2\n", ".csv")
    plane.get_raw_object.assert_called_once_with(
        OwnerScope("user", "user-1"), "chat_files/thread-9/file-7.csv",
    )


def test_get_raw_file_missing_record_returns_none():
    from backend.services import chat_file_service
    with patch.object(chat_file_service, "get_file", return_value=None):
        assert chat_file_service.get_raw_file("user-1", "file-7") is None


def test_get_raw_file_missing_object_returns_none():
    from backend.services import chat_file_service
    plane = MagicMock()
    plane.get_raw_object.return_value = None
    file_data = {"thread_id": "thread-9", "original_name": "report.xlsx"}
    with patch.object(chat_file_service, "get_file", return_value=file_data), \
         patch("backend.services.data_plane_service.get_default_plane", return_value=plane):
        assert chat_file_service.get_raw_file("user-1", "file-7") is None
