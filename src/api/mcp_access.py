"""Verify tool transport credentials before touching private services."""
from fastapi import HTTPException
from api.security import verify_token


def patient_actor(token: str, user_id: str | None = None, session_id: str | None = None, create: bool = False):
    try:
        principal = verify_token(token)
        if principal.role != "patient" or (user_id is not None and user_id != principal.sub):
            raise PermissionError("Patient identity must match the signed-in account")
        from api.routers.patients import _find_by_id
        patient = _find_by_id(principal.sub)
        if patient is None or not patient.active:
            raise PermissionError("An active patient account is required")
        if session_id is not None:
            from api.routers.chat_sessions import ensure_session_owner
            ensure_session_owner(principal.sub, session_id, create)
        return principal
    except HTTPException as exc:
        raise PermissionError("Authentication or ownership check failed") from exc


def admin_actor(token: str):
    try:
        principal = verify_token(token)
    except HTTPException as exc:
        raise PermissionError("Authentication required") from exc
    if principal.role != "admin":
        raise PermissionError("Administrator role required")
    return principal
