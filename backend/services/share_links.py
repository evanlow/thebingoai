"""Reusable public-share-link mechanics: token mint/hash, race-safe upsert,
token resolution.

Extracted from api/briefing_shares.py so future share surfaces (e.g. dashboard
shares) reuse the easy-to-get-wrong parts instead of rewriting them. Content
freezing, create-time guards, and HTTP policy (generic 404s) stay with each
caller — they are resource-specific.

Contract for `model`: a unique `token_hash` column plus a unique FK to the
shared resource, so a concurrent first-enable manifests as IntegrityError on
commit. No FastAPI imports here — callers map RuntimeError to HTTP 500.
"""

import hashlib
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def mint_token() -> str:
    """32 bytes urandom, URL-safe base64. Returned once; never stored raw."""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upsert_share(db: Session, model, filters, make_row, refresh) -> str:
    """Enable (or rotate) a share link. Returns the raw token — the only time
    it is ever derivable; only sha256(token) is stored.

    filters: SQLAlchemy clauses identifying the one row for the resource.
    make_row(): new unsaved `model` instance with frozen content (token_hash
    is set here, not by the caller).
    refresh(row): re-freeze content onto an existing row, so re-sharing always
    freezes today's view.

    Re-enabling rotates the token: the previous link dies immediately. If two
    concurrent first-time enables race, the loser's INSERT hits IntegrityError;
    it rolls back, re-queries the winner's row and rotates the token onto it —
    it cannot recover the winner's raw token. Raises RuntimeError if the row
    vanished after the race.
    """
    token = mint_token()
    row = db.query(model).filter(*filters).first()
    if row is None:
        row = make_row()
        db.add(row)
    else:
        refresh(row)
    row.token_hash = hash_token(token)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.query(model).filter(*filters).first()
        if row is None:
            raise RuntimeError("share row disappeared after losing insert race")
        refresh(row)
        row.token_hash = hash_token(token)
        db.commit()
    return token


def resolve_by_token(db: Session, model, token: str):
    """Token -> row, or None. The caller owns the (generic) 404 policy."""
    return db.query(model).filter(model.token_hash == hash_token(token)).first()
