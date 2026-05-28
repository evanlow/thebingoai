"""Generic cron-dispatch helper — eliminates copy-paste across dispatchers."""
import logging
from datetime import datetime, timezone
from typing import Callable, Type, Any

from sqlalchemy.orm import Session

from backend.utils.cron import compute_next_run

logger = logging.getLogger(__name__)


def dispatch_due_rows(
    db: Session,
    *,
    model_cls: Type,
    enabled_field: str,        # attribute name for the "active" boolean
    cron_field: str,           # attribute name for the cron expression
    next_run_field: str,       # attribute name for next_run_at
    dispatch_fn: Callable,     # called with (row) → must enqueue the Celery task
    now: datetime | None = None,
    stagger_seconds: float = 0.0,
) -> int:
    """Dispatch all due rows for one cron-scheduled model.

    Mutates next_run_at on each row using the row's own ``timezone`` attribute
    (if present) so cron expressions are honored in the user's local time.
    Caller is responsible for committing the session.
    """
    if now is None:
        now = datetime.utcnow()
    # `now` is used both for SQL comparison (naive UTC) and as the reference
    # instant for the next-run computation (tz-aware UTC).
    now_utc_aware = now if now.tzinfo else now.replace(tzinfo=timezone.utc)

    enabled_col = getattr(model_cls, enabled_field)
    next_run_col = getattr(model_cls, next_run_field)

    due = (
        db.query(model_cls)
        .filter(enabled_col == True, next_run_col <= now)
        .all()
    )

    if not due:
        return 0

    for i, row in enumerate(due):
        try:
            dispatch_fn(row)
            cron_expr = getattr(row, cron_field)
            if cron_expr:
                tz_name = getattr(row, "timezone", None) or "UTC"
                setattr(
                    row,
                    next_run_field,
                    compute_next_run(cron_expr, tz_name, now_utc=now_utc_aware),
                )
        except Exception as exc:
            logger.error("dispatch_due_rows: failed for %s id=%s: %s", model_cls.__name__, getattr(row, "id", "?"), exc)

    return len(due)
