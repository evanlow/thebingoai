"""profile_chat_file reads dataset raw via the per-user plane, not DO."""
import json
from unittest.mock import MagicMock, patch


def test_profile_chat_file_reads_via_get_raw_file():
    from backend.tasks import profiling_tasks

    file_id = "file-7"
    file_data = {
        "file_id": file_id,
        "user_id": "user-1",
        "thread_id": "thread-9",
        "mime_type": "text/csv",
        "original_name": "report.csv",
        "metadata": {},
        "storage_key": "chat_files/thread-9/file-7.csv",
    }

    fake_redis = MagicMock()
    fake_redis.get.return_value = json.dumps(file_data)
    fake_redis.ttl.return_value = 3600

    with patch("redis.from_url", return_value=fake_redis), \
         patch("backend.services.chat_file_service.get_raw_file",
               return_value=(b"a,b\n1,2\n", ".csv")) as get_raw, \
         patch("backend.profiler.dataset_profiler.profile_dataframe") as prof:
        prof.return_value.to_prompt_text.return_value = "PROFILE"
        profiling_tasks.profile_chat_file(file_id)

    get_raw.assert_called_once_with("user-1", file_id)
    # The updated record persisted back to Redis carries the profile text + ready
    saved = json.loads(fake_redis.setex.call_args[0][2])
    assert saved["profile_text"] == "PROFILE"
    assert saved["profile_status"] == "ready"


def test_profile_chat_file_missing_raw_marks_ready_without_text():
    from backend.tasks import profiling_tasks

    file_data = {
        "file_id": "file-7", "user_id": "user-1", "thread_id": "thread-9",
        "mime_type": "text/csv", "original_name": "report.csv", "metadata": {},
    }
    fake_redis = MagicMock()
    fake_redis.get.return_value = json.dumps(file_data)
    fake_redis.ttl.return_value = 3600

    with patch("redis.from_url", return_value=fake_redis), \
         patch("backend.services.chat_file_service.get_raw_file", return_value=None):
        profiling_tasks.profile_chat_file("file-7")

    saved = json.loads(fake_redis.setex.call_args[0][2])
    assert saved["profile_status"] == "ready"
    assert "profile_text" not in saved
