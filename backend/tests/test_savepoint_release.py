"""_try_insert releases its SAVEPOINT on success so a large batch commits.

Before the fix, each successful insert left an open nested savepoint; the outer
commit released ~N of them recursively and overflowed Python's recursion limit
(RecursionError) once N approached ~1000. This drives well past that.
"""
import uuid

from backend.services.template_materializer import _try_insert
from backend.models.user import User


def test_large_batch_commits_without_recursionerror(db_session):
    n = 1500  # > Python's default recursion limit (~1000)
    for _ in range(n):
        u = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4()}@example.com", auth_provider="sso")
        assert _try_insert(db_session, u) is True

    # Before the fix this raised RecursionError while releasing ~1500 savepoints.
    db_session.commit()

    assert db_session.query(User).count() >= n
