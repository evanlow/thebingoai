"""Tests for tombstone_account — the deletion teardown must leave nothing armed."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.services.account_deletion import tombstone_account


def _db_recording_updates(updates: list):
    """MagicMock db whose .query(Model)…update(values) calls land in `updates`
    as (Model, values) pairs. The query mock is self-returning so filter chains
    of any depth resolve back to the same object."""
    db = MagicMock()

    def _query(model):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None          # org lookup: no rename needed
        q.update.side_effect = lambda values, **kw: (
            updates.append((model, values)) or 1
        )
        return q

    db.query.side_effect = _query
    return db


def test_tombstone_disables_pipeline_schedules():
    """A tombstoned pipeline's schedules must be disarmed too — otherwise
    re-enabling the pipeline resurrects a cron the deletion was meant to stop."""
    from backend.models.pipeline import Pipeline, PipelineSchedule

    updates: list = []
    db = _db_recording_updates(updates)
    user = SimpleNamespace(id="u-1", email="real@example.com", is_active=True, org_id="org-1")

    tombstone_account(db, user, "masked-123@example.com")

    by_model = {model: values for model, values in updates}
    assert Pipeline in by_model
    assert PipelineSchedule in by_model
    assert by_model[PipelineSchedule][PipelineSchedule.enabled] is False
    assert by_model[PipelineSchedule][PipelineSchedule.next_run_at] is None


def test_tombstone_masks_user_and_commits():
    updates: list = []
    db = _db_recording_updates(updates)
    user = SimpleNamespace(id="u-1", email="real@example.com", is_active=True, org_id="org-1")

    tombstone_account(db, user, "masked-123@example.com")

    assert user.email == "masked-123@example.com"
    assert user.is_active is False
    db.commit.assert_called_once()
