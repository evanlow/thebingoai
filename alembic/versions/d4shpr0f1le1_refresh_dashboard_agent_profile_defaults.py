"""Refresh seeded dashboard_agent profile sections to the new defaults.

Users whose dashboard_agent AgentProfile still carries an *unmodified*
historical default (identity/soul/tools/guardrails) get that section swapped
for the current default from `backend.agents.profile_defaults`. Sections the
user edited never hash-match a historical default and are left untouched.
`published_snapshot` values are refreshed the same way so the live render
path picks up the new text immediately.

Matching is by SHA-256 of the stored text against every historical default
variant extracted from git history of profile_defaults.py (9 tools variants,
2 identity, 1 soul, 3 guardrails).

Revision ID: d4shpr0f1le1
Revises: s1emantic0a1b
Create Date: 2026-07-17
"""
import hashlib
import json
import logging

import sqlalchemy as sa
from alembic import op

revision = "d4shpr0f1le1"
down_revision = "s1emantic0a1b"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

# SHA-256 digests of every historical default text per section (from git
# history of backend/agents/profile_defaults.py — the literals themselves are
# too large to embed).
_OLD_DEFAULT_HASHES = {
    "identity": {
        "4cd6890d1a970d909edfbd73bfcbfaf10bcadc26bd4629e05e63c7090748b76e",
        "500f15e95558a3dbf9160290022f167d6c1f3ad7a4f4683ca7451478ec98ae8b",
    },
    "tools": {
        "2b9705c2b0b365d47cc2ae2cb982eabbf81fc4e7d958990fe327b15c821e4d35",
        "6f7b648a1bec1bcb5e41cc691c15b5dbe9c9893eb075ddfbfd86d80e06f19107",
        "79225d0860791536da5e02b92674e2f5b53a6da7182ad50d7190b9bcfa990632",
        "98dd15eb703d21fcbe9acc8fa2fda5910e4405edca258b5396dffd43c73be67e",
        "c185d6ac5c4707b27a49b801c1dd9eb76204a8e128068389e0560f3acbcd2f00",
        "c7efd19c965b634a7d7e0b22a99e8eef6cd84bd9ba2bfe6e6653924c508e0092",
        "e7ef7b6fe56869707a33b517a4cf629fa71b1960c068aa986f96fd529cc29126",
        "eb568eb0f71d3019f5df83107bad16769322b2b8d6d40264d5bb80ec054c7338",
        "fe649267fd2552c9a4e82b7ceb847463f6c236db003fe1971c7ee4de9314492e",
    },
    "soul": {
        "8ee5c6d88dd1dd81e329a1750e93eb186ab74782e52f6320a62d008dea241dc1",
    },
    "guardrails": {
        "59291abc3c7a085ba45e8d58435f8e70813b3402af82ee10b09e16b0685aeaae",
        "781a2e93b1065ebdf41fc1f619cea7b277272e596b29f883bcab7521404c578d",
        "d10f5fdba9fe52cb59b79efe5d161963fe3d9811efd3a083e9545b1ec2a4663f",
    },
}


def _is_old_default(section: str, text) -> bool:
    if not isinstance(text, str) or not text:
        return False
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest in _OLD_DEFAULT_HASHES[section]


def upgrade() -> None:
    # Import the finalized new defaults from the app (alembic/env.py puts the
    # repo root on sys.path). Single source — no duplicated prompt text here.
    from backend.agents.profile_defaults import DEFAULTS

    new = DEFAULTS["dashboard_agent"]
    sections = ("identity", "soul", "tools", "guardrails")

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, identity, soul, tools, guardrails, published_snapshot "
            "FROM agent_profiles WHERE agent_type = 'dashboard_agent'"
        )
    ).mappings().all()

    touched = 0
    for row in rows:
        updates = {}
        for section in sections:
            if _is_old_default(section, row[section]):
                updates[section] = new[section]

        snapshot = row["published_snapshot"]
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except ValueError:
                snapshot = None
        if isinstance(snapshot, dict):
            snap_changed = False
            for section in sections:
                if _is_old_default(section, snapshot.get(section)):
                    snapshot[section] = new[section]
                    snap_changed = True
            if snap_changed:
                updates["published_snapshot"] = json.dumps(snapshot)

        if not updates:
            continue
        touched += 1
        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        conn.execute(
            sa.text(f"UPDATE agent_profiles SET {set_clause} WHERE id = :id"),
            {**updates, "id": row["id"]},
        )

    logger.info(
        "dashboard_agent profile defaults refresh: %d of %d rows updated",
        touched,
        len(rows),
    )


def downgrade() -> None:
    # Data-only prompt refresh; the historical texts are not stored here, so
    # downgrade is a documented no-op (same precedent as y9a0b1c2d3e4).
    pass
