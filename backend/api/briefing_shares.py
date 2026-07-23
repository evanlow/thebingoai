"""Public share links for briefings.

Tokens: 32 bytes urandom, URL-safe base64, sha256-hashed at rest. The raw
token is returned ONCE at create time and is never re-derivable from the DB.
Mirrors plugins/bingo-org-governance/bingo_org_governance/invites.py.

The POST guard (ready + widget_snapshots present) is load-bearing: it is why
GET /api/public/briefings/{token} can serve stored JSON and never run SQL.
"""

import logging
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.briefing import Briefing
from backend.models.briefing_share import BriefingShare
from backend.models.dashboard import Dashboard
from backend.schemas.briefing import PublicBriefingResponse, strip_widget
from backend.services.share_links import (
    hash_token as _hash,  # test_briefing_shares.py imports _hash from this module
    resolve_by_token,
    upsert_share,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["briefing-shares"])


def _referenced_widget_ids(payload: dict | None) -> set:
    return {
        str(s["widget_id"])
        for s in (payload or {}).get("sections", [])
        if isinstance(s, dict) and s.get("widget_id")
    }


def _owned_briefing(db: Session, briefing_id: int, user: User) -> Briefing:
    b = (
        db.query(Briefing)
        .filter(Briefing.id == briefing_id, Briefing.user_id == user.id)
        .first()
    )
    if b is None:
        # 404 not 403 — do not confirm the briefing exists to a non-owner.
        raise HTTPException(status_code=404, detail="Briefing not found")
    return b


@router.post("/briefings/{briefing_id}/share", status_code=201)
async def create_share(
    briefing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable (or rotate) the public link for a briefing. Returns the raw token once."""
    b = _owned_briefing(db, briefing_id, current_user)

    if b.status != "ready" or not b.payload:
        raise HTTPException(status_code=400, detail="Only a ready briefing can be shared")

    # Load-bearing: without inline snapshots the public view would fall back to
    # a live SQL re-query. Refusing here is what keeps the anonymous path
    # structurally incapable of querying. Do not relax.
    #
    # Gated on the briefing actually referencing widgets: generation only writes
    # widget_snapshots when at least one section carries a widget_id, so a
    # text-only briefing legitimately has none — and with no embeds there is no
    # SQL-fallback risk to guard against.
    referenced = _referenced_widget_ids(b.payload)
    if referenced and not (b.payload or {}).get("widget_snapshots"):
        raise HTTPException(
            status_code=400,
            detail="This briefing predates chart snapshots and can't be shared. "
                   "Generate a fresh one.",
        )

    def _freeze():
        """Build the frozen public view from the dashboard as it looks right
        now. Called at every point a token is (re)minted so re-sharing always
        freezes today's view. See resolve_share for why the `wid in snapshots`
        gate must be preserved exactly."""
        snapshots = (b.payload or {}).get("widget_snapshots") or {}
        dashboard = db.query(Dashboard).filter(Dashboard.id == b.dashboard_id).first()
        widgets_by_id = {str(w.get("id")): w for w in ((dashboard.widgets if dashboard else None) or [])}
        referenced = {str(s["widget_id"]) for s in (b.payload or {}).get("sections", []) if s.get("widget_id")}
        frozen = {
            wid: strip_widget(widgets_by_id[wid])
            for wid in referenced
            if wid in widgets_by_id and wid in snapshots
        }
        return frozen, (dashboard.title if dashboard else None)

    def _make_row():
        widgets_frozen, dashboard_name = _freeze()
        return BriefingShare(
            id=str(_uuid.uuid4()),
            briefing_id=b.id,
            created_by_user_id=current_user.id,
            widgets_frozen=widgets_frozen,
            dashboard_name=dashboard_name,
        )

    def _refresh(share):
        share.widgets_frozen, share.dashboard_name = _freeze()

    try:
        # Rotation + concurrent-first-enable race recovery live in the shared
        # helper; the comments explaining WHY are on upsert_share itself.
        token = upsert_share(
            db,
            BriefingShare,
            [BriefingShare.briefing_id == b.id],
            _make_row,
            _refresh,
        )
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to create share link")

    logger.info("briefing %s share link enabled by user %s", b.id, current_user.id)
    # No server-built URL: this endpoint is only ever called from a browser,
    # which already knows its own origin. See stores/auth.ts's
    # window.location.origin pattern for our-own-app URLs handed to a user.
    return {"token": token}


@router.get("/briefings/{briefing_id}/share")
async def get_share_status(
    briefing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Whether a public link is active. Only sha256(token) is stored, so the
    URL itself is not re-derivable — the frontend uses this to show the shared
    state after a reload and offer 'new link' (rotate) or 'turn off', instead
    of silently rotating a link the owner already distributed."""
    b = _owned_briefing(db, briefing_id, current_user)
    active = (
        db.query(BriefingShare.id).filter(BriefingShare.briefing_id == b.id).first()
        is not None
    )
    return {"active": active}


@router.delete("/briefings/{briefing_id}/share", status_code=204)
async def delete_share(
    briefing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the public link. Idempotent."""
    b = _owned_briefing(db, briefing_id, current_user)
    db.query(BriefingShare).filter(BriefingShare.briefing_id == b.id).delete(
        synchronize_session=False
    )
    db.commit()
    logger.info("briefing %s share link revoked by user %s", b.id, current_user.id)
    return Response(status_code=204)


# The ONLY unauthenticated router in the application. Kept under its own
# /public prefix so the anonymous surface is greppable and can be rate-limited
# or WAF'd as one path later.
public_router = APIRouter(prefix="/public", tags=["public"])


class ResolveShareRequest(BaseModel):
    token: str


@public_router.post("/briefings/resolve", response_model=PublicBriefingResponse)
async def resolve_share(req: ResolveShareRequest, db: Session = Depends(get_db)):
    """Resolve a share token to its briefing. No auth. Serves stored JSON only —
    never a connector, never SQL. Guaranteed by the POST /share guard.

    The token travels in the POST body, never the URL path: uvicorn/nginx
    access logs record request paths verbatim, so a path token would land the
    raw credential in ordinary logs, defeating hashed-at-rest storage. The
    browser side keeps it out of server-visible URLs too (fragment, see
    pages/share/briefings/index.vue)."""
    share = resolve_by_token(db, BriefingShare, req.token)
    if share is None:
        # Generic 404 — do not distinguish never-existed from revoked.
        raise HTTPException(status_code=404, detail="This link isn't available")

    b = db.query(Briefing).filter(Briefing.id == share.briefing_id).first()
    if b is None or b.status != "ready" or not b.payload:
        raise HTTPException(status_code=404, detail="This link isn't available")

    payload = b.payload or {}
    snapshots = payload.get("widget_snapshots") or {}

    # The create-time guard only proves widget_snapshots existed on the request
    # that made the share. Re-check it here: without this, a briefing whose
    # payload was mutated after sharing (or a legacy row from before the guard
    # existed) would silently degrade to widget_snapshots={}, which is exactly
    # the "absent" signal the frontend uses to fall back to a live SQL refresh —
    # the one thing this endpoint exists to prevent. Text-only briefings
    # (no referenced widgets → no embeds → no fallback risk) pass with {}.
    if _referenced_widget_ids(payload) and not snapshots:
        raise HTTPException(status_code=404, detail="This link isn't available")

    # Widget shape and dashboard name are NOT read live — they were frozen onto
    # the share row at share time (create_share._freeze). This endpoint must
    # never query `dashboards`: a briefing is an immutable snapshot, but
    # dashboard.widgets[].widget.config is not (the frontend merges refreshed
    # rows into it and saves), so reading it live here would let a share link
    # serve data newer than what the owner reviewed, and a later rename/edit
    # would silently change what an old link shows.
    #
    # Re-apply strip_widget and the `wid in snapshots` gate here, over the
    # already-frozen data, even though _freeze() applied both at mint time.
    # The freeze is about DATA (never serve dashboard state newer than what
    # was reviewed) — it must not also freeze the redaction POLICY. If
    # _PUBLIC_WIDGET_KEYS is tightened later to close a leak, every
    # already-minted link must pick up the tighter allowlist without needing
    # to be re-shared. strip_widget is an allowlist over top-level keys, so
    # re-applying it to already-stripped data is idempotent.
    widgets = {
        wid: strip_widget(w)
        for wid, w in (share.widgets_frozen or {}).items()
        if wid in snapshots
    }

    try:
        return PublicBriefingResponse(
            headline=payload["headline"],
            deck=payload["deck"],
            kpis=payload.get("kpis", []),
            sections=payload["sections"],
            key_takeaways=payload["key_takeaways"],
            recommended_actions=payload.get("recommended_actions"),
            widget_snapshots=snapshots,
            widgets=widgets,
            dashboard_name=share.dashboard_name,
            created_at=b.created_at,
        )
    except (KeyError, ValidationError):
        # Malformed/legacy payload: a missing required field raises KeyError,
        # a present-but-invalid one (deck=None, section prose=None) raises
        # pydantic ValidationError. Same generic 404 as every other failure —
        # a 500 here would tell an attacker the token was valid (unknown
        # tokens 404 too).
        raise HTTPException(status_code=404, detail="This link isn't available")
