"""
Voice endpoints — issue LiveKit access tokens so the browser SPA can
join a room and talk to the voice agent worker.

Flow:

    Browser ── POST /voice/token ──▶ this router
                                       │ signs JWT with LIVEKIT_API_*
                                       ▼
                            { token, url, room, identity }
    Browser ── livekit-client.connect(url, token) ──▶ LiveKit Cloud
                                       │
                                       ▼
                            Voice worker (src/voice/run.py)
                            is dispatched into the room
                            and runs the LangGraph agent.

Token TTL is short (10 minutes) — clients refresh on reconnect.

Environment variables required (already used by ``voice/run.py``):
    LIVEKIT_URL          wss://your-project.livekit.cloud
    LIVEKIT_API_KEY
    LIVEKIT_API_SECRET
"""

from __future__ import annotations

import os
import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from api.security import require_principal
from pydantic import BaseModel, Field

try:
    # Provided by ``livekit-api`` (transitive dep of livekit-agents).
    from livekit import api as livekit_api
except ImportError:  # pragma: no cover — should be present in production
    livekit_api = None  # type: ignore[assignment]


router = APIRouter(prefix="/voice", tags=["Voice"])


# ── Schemas ────────────────────────────────────────────────────


class TokenRequest(BaseModel):
    """Optional identity hint must match the verified account. Rooms are server assigned."""

    user_id: Optional[str] = Field(
        default=None,
        description="Stable user identifier used as the LiveKit participant identity. "
        "If omitted, a random one is generated.",
    )
    room: Optional[str] = Field(
        default=None,
        description="Room name to join. If omitted, a fresh per-session room is created.",
    )
    name: Optional[str] = Field(
        default=None,
        description="Display name visible to other participants (currently just the agent).",
    )


class TokenResponse(BaseModel):
    url: str = Field(..., description="WebSocket URL of the LiveKit project.")
    token: str = Field(..., description="Signed access JWT for ``livekit-client``.")
    room: str = Field(..., description="Room the client should join.")
    identity: str = Field(..., description="Participant identity that was signed into the token.")


# ── Endpoint ───────────────────────────────────────────────────


@router.post("/token", response_model=TokenResponse)
async def issue_token(req: TokenRequest, request: Request) -> TokenResponse:
    """
    Issue a short-lived LiveKit access token for the browser.

    The voice worker (running in a separate process / container) is
    dispatched into the same room by LiveKit Cloud automatically when
    a participant joins, so the browser only needs this one call.
    """
    if livekit_api is None:
        raise HTTPException(
            status_code=503,
            detail="livekit-api not installed on the server",
        )

    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not (url and api_key and api_secret):
        raise HTTPException(
            status_code=500,
            detail="LiveKit not configured — set LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET",
        )

    principal = require_principal(request)
    if req.user_id is not None and req.user_id != principal.sub:
        raise HTTPException(403, "Voice identity must match the signed-in account")
    if req.room is not None:
        raise HTTPException(403, "Voice rooms are assigned by the server")
    identity = principal.sub
    room = f"voice-{uuid.uuid4().hex}"
    display_name = request.state.patient.full_name
    ttl = min(600, principal.expires_at - int(time.time()))
    if ttl <= 0:
        raise HTTPException(401, "Sign-in expired")
    metadata = {"health_authenticated": True, "patient_id": identity, "auth_expires_at": int(time.time()) + ttl, "account_version": principal.account_version}

    grants = livekit_api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
        can_update_own_metadata=False,
    )

    token = (
        livekit_api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(display_name)
        .with_metadata(json.dumps(metadata))
        .with_grants(grants)
        .with_ttl(__import__("datetime").timedelta(seconds=ttl))
        .to_jwt()
    )

    return TokenResponse(url=url, token=token, room=room, identity=identity)
